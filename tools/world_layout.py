"""Generate the runtime's camp pools and table checks from the owner's own game exports.

usage: world_layout.py <exports DataObject/Field root> <world-census.csv> <out dir: repo root> [--max-size-step N] [--max-hp-ratio R]

Writes runtime/Native/src/reviewed_layout.hpp (offsets, names and fingerprints), runtime/Scripts/world_pools.lua and
docs/world-pools.csv. Nothing from a game asset is embedded beyond those derived facts.

Which fights are eligible is decided here and nowhere else. A camp must be generic: it respawns on a timer, has no
waves or external enemies, no rare or demo enemies, and no other table refers to it except to switch it on or off.
Anything else, including every quest, story, assignment and boss fight, is not in the output, so the mod cannot touch it.
"""
import argparse, csv, hashlib, json, re, struct, collections
from pathlib import Path

OPEN_WORLD = ["1100-MIDGA", "1200-GRASA", "1300-JUNOA", "2200-CORLA", "2400-GONGA", "2500-CSMOA", "2600-NIBLA"]
SWITCHES = {"ObjectEnemyTerritory", "LocationProgrammer", "ObjectEntryAttributeList", "StateChange", "ResidentObject", "ResidentStateChange", "Object"}
EXCLUDED_WORDS = ("demo", "media", "quest", "story", "boss", "subjug", "_mg_", "dummy", "rare", "test", "chocoquest")


def eligible(r):
    if r["region"] not in OPEN_WORLD or r["respawn"] in ("", "0") or not r["templates"]:
        return False
    if r["rare"] == "1" or r["waves"] != "0" or r["external"] != "0" or r["blueprint"]:
        return False
    if any(w in (r["territory"] + "|" + r["templates"]).lower() for w in EXCLUDED_WORDS):
        return False
    tables = {x.split("/")[-1] for x in r["refs"].split(";") if x}
    return tables <= SWITCHES


def biome(r):
    """Enemies only move between camps of the same stretch of land, so desert enemies stay out of the sea coast."""
    name = r["territory"]
    for marker, label in (("swampmob", "swamp"), ("midgamob", "midgar")):
        if marker in name:
            return f"{r['region']}:{label}"
    m = re.match(r"(.+?)_?mob_", name, re.I)
    return f"{r['region']}:{(m.group(1) if m else name).rstrip('_').lower()}"


def layout(path, expect_rows):
    data = path.read_bytes()
    u32 = lambda p: struct.unpack_from("<I", data, p)[0]
    names = []; p = u32(0x18); end = p + u32(0x1c)
    while p < end:
        wide = data[p] & 0x80; length = ((data[p] & 0x7f) << 8) | data[p + 1]; p += 2
        count = length * (2 if wide else 1)
        names.append(data[p:p + count].decode("utf-16-le" if wide else "latin-1")); p += count
    export = u32(0x34) + u32(0x38); base = export + 0x20; size = u32(export + 0xc)
    image = bytearray(data[base:base + size])
    patches = {}; p = base + size + 8; count = u32(p); p += 4
    for _ in range(count):
        name, number, n = struct.unpack_from("<iii", data, p); p += 12
        if not 0 <= name < len(names) or number < 0:
            raise ValueError("invalid name patch")
        for _ in range(n):
            offset = u32(p); p += 4
            if not 0 <= offset <= size - 8 or offset in patches:
                raise ValueError("invalid patch offset")
            patches[offset] = names[name] if number == 0 else f"{names[name]}_{number - 1}"
            image[offset:offset + 8] = b"\0" * 8
    val = lambda p: struct.unpack_from("<I", image, p)[0]
    def ptr(p):
        value = struct.unpack_from("<q", image, p)[0]
        if value & 1 != 1:
            raise ValueError("expected a frozen relative pointer")
        target = p + (value >> 1)
        if not 0 <= target < size:
            raise ValueError("pointer outside the frozen image")
        return target
    rows, entries_count, prop_count = val(8), val(0x50), val(0x40)
    if rows != expect_rows or entries_count != rows:
        raise ValueError(f"unexpected table dimensions {rows} {entries_count} in {path}")
    keys = ptr(0); entries = ptr(0x48); properties = ptr(0x38)
    indices = {patches[keys + 20 * i]: val(keys + 20 * i + 8) for i in range(rows)}
    if sorted(indices.values()) != list(range(rows)):
        raise ValueError("unexpected row indices")
    sizes = {1: 1, 2: 1, 3: 1, 4: 2, 6: 4, 7: 4, 8: 8, 9: 4, 10: 16, 11: 8}
    fields = {}; offset = 0; maximum = 1
    align = lambda x, a: (x + a - 1) // a * a
    for i in range(prop_count):
        record = properties + 12 * i; name = patches[record]; kind = val(record + 8); array = name.endswith("_Array")
        alignment = 8 if array or kind == 10 else 4 if kind == 11 else sizes[kind]
        offset = align(offset, alignment); fields[name] = offset
        offset += 16 if array else sizes[kind]; maximum = max(maximum, alignment)
    stride = align(offset, maximum)
    out = {}
    for name, index in indices.items():
        descriptor = entries + stride * index + fields["MobTemplateList_Array"]
        count, capacity = val(descriptor + 8), val(descriptor + 12)
        if count == 0:
            continue
        vector = ptr(descriptor)
        out[name] = {"descriptor": descriptor, "vector": vector, "templates": [patches[vector + 8 * k] for k in range(count)], "count": count}
    return {"bytes": size, "sha": hashlib.sha256(image).hexdigest(), "patches": sorted(patches.items()), "rows": out}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("field_root", type=Path); ap.add_argument("census", type=Path); ap.add_argument("repo", type=Path)
    ap.add_argument("--max-size-step", type=int, default=None); ap.add_argument("--max-hp-ratio", type=float, default=None)
    args = ap.parse_args()
    census = list(csv.DictReader(args.census.open(encoding="utf-8")))
    by_region = collections.defaultdict(list)
    for r in census:
        by_region[r["region"]].append(r)
    camps = [r for r in census if eligible(r)]
    roster = collections.defaultdict(list)
    for r in camps:
        roster[biome(r)].append(r)
    tables = []; report = []
    stats = collections.Counter(); varied = collections.Counter()
    for region in OPEN_WORLD:
        lay = layout(args.field_root / region / "EnemyTerritory.uasset", len(by_region[region]))
        targets = []
        for r in [c for c in camps if c["region"] == region]:
            row = lay["rows"].get(r["territory"])
            if not row or row["templates"] != r["templates"].split("|"):
                raise ValueError(f"census and table disagree for {r['territory']}")
            sizes, moves = r["sizes"].split("|"), r["moves"].split("|")
            pops = [int(x) for x in r["pop_max"].split("|")] if r["pop_max"] else [1] * len(sizes)
            pops = (pops + [1] * len(sizes))[:len(sizes)]
            hps = [float(x) if x not in ("", "?") else 0 for x in r["hp"].split("|")]
            budget = sum(p * h for p, h in zip(pops, hps))
            options = [(row["vector"], tuple(row["templates"]))]
            seen = {tuple(row["templates"])}
            for donor in roster[biome(r)]:
                t = tuple(donor["templates"].split("|"))
                if t in seen or len(t) != len(sizes):
                    continue
                dsizes, dmoves = donor["sizes"].split("|"), donor["moves"].split("|")
                if dmoves != moves:
                    continue
                if args.max_size_step is not None and any(abs(int(a) - int(b)) > args.max_size_step for a, b in zip(dsizes, sizes)):
                    continue
                dhps = [float(x) if x not in ("", "?") else 0 for x in donor["hp"].split("|")]
                if args.max_hp_ratio and budget and sum(p * h for p, h in zip(pops, dhps)) > args.max_hp_ratio * budget:
                    continue
                seen.add(t)
                options.append((lay["rows"][donor["territory"]]["vector"], t))
            stats[region] += 1
            if len(options) > 1:
                varied[region] += 1
                targets.append({"id": r["territory"], "descriptor": row["descriptor"], "options": options})
            report.append({"region": region, "biome": biome(r), "camp": r["territory"], "original": "|".join(row["templates"]),
                           "alternatives": len(options) - 1, "options": " ; ".join("|".join(o[1]) for o in options[1:])})
        tables.append({"region": region, "asset": f"/Game/DataObject/Field/{region}/EnemyTerritory.EnemyTerritory", "bytes": lay["bytes"], "sha": lay["sha"],
                       "patches": lay["patches"], "targets": targets})
    q = lambda s: "L" + json.dumps(s, ensure_ascii=True)
    h = ["// Generated by tools/world_layout.py from the owner's own exports. Offsets, names and fingerprints only.",
         "#pragma once", "#include <cstddef>", "#include <cstdint>", "namespace reviewed {",
         "struct NamePatch {std::uint32_t offset;const wchar_t* name;};",
         "struct Target {const wchar_t* id;std::uint32_t descriptor;const std::uint32_t* options;std::uint32_t option_count;};",
         "struct Table {const wchar_t* asset;std::size_t image_bytes;const char* masked_sha256;const NamePatch* names;std::size_t name_count;const Target* targets;std::size_t target_count;};"]
    for i, t in enumerate(tables):
        h.append(f"constexpr NamePatch names{i}[]={{" + ",".join(f"{{{o},{q(n)}}}" for o, n in t["patches"]) + "};")
        for j, c in enumerate(t["targets"]):
            h.append(f"constexpr std::uint32_t options{i}_{j}[]={{" + ",".join(str(o[0]) for o in c["options"]) + "};")
        h.append(f"constexpr Target targets{i}[]={{" + ",".join(f"{{{q(c['id'])},{c['descriptor']},options{i}_{j},{len(c['options'])}}}" for j, c in enumerate(t["targets"])) + "};")
    h.append("constexpr Table tables[]={")
    for i, t in enumerate(tables):
        h.append(f"    {{{q(t['asset'])},{t['bytes']},{json.dumps(t['sha'])},names{i},{len(t['patches'])},targets{i},{len(t['targets'])}}},")
    h += ["};", f"constexpr std::size_t table_count={len(tables)};", "}"]
    (args.repo / "runtime/Native/src/reviewed_layout.hpp").write_text("\n".join(h) + "\n", encoding="utf-8")
    l = ["-- Generated by tools/world_layout.py. Which camps may change, and how many compositions each has.", "return {"]
    for t in tables:
        l.append(f"  {{asset={json.dumps(t['asset'])},region={json.dumps(t['region'])},camps={{")
        l += [f"    {{id={json.dumps(c['id'])},options={len(c['options'])}}}," for c in t["targets"]]
        l.append("  }},")
    l.append("}")
    (args.repo / "runtime/Scripts/world_pools.lua").write_text("\n".join(l) + "\n", encoding="utf-8")
    with (args.repo / "docs/world-pools.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["region", "biome", "camp", "original", "alternatives", "options"]); w.writeheader(); w.writerows(report)
    total = sum(stats.values()); var = sum(varied.values())
    print(f"eligible camps {total}, with a choice {var}, average options {sum(r['alternatives'] + 1 for r in report) / max(total, 1):.1f}")
    print({k: f"{varied[k]}/{stats[k]}" for k in OPEN_WORLD})
    print("excluded:", collections.Counter(r["region"] for r in census if r["region"] in OPEN_WORLD and not eligible(r)).most_common())


if __name__ == "__main__":
    main()
