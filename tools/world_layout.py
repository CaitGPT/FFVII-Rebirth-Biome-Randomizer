"""Generate the runtime's camp pools and table checks from the owner's own game exports.

usage: world_layout.py <exports DataObject/Field root> <world-census.csv> <out dir: repo root>

Writes runtime/Native/src/reviewed_layout.hpp (offsets, names and fingerprints), runtime/Scripts/world_pools.lua and
docs/world-pools.csv. Nothing from a game asset is embedded beyond those derived facts.

A camp's slots can each hold any enemy from its stretch of land that moves the same way (ground, flying, and so on), at
any size, and its total can be any count its region's generic camps span. A region's Combat Assignment enemies join the
same-movement slots once the player has won that assignment.

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
        row = {"descriptor": descriptor, "vector": vector, "templates": [patches[vector + 8 * k] for k in range(count)], "count": count}
        for field, key in (("MinPopList_Array", "min"), ("MaxPopList_Array", "max")):
            d = entries + stride * index + fields[field]
            n = val(d + 8)
            # Counts are one byte each.
            row[key] = {"descriptor": d, "vector": ptr(d) if n else None, "values": [image[ptr(d) + k] for k in range(n)] if n else []}
        out[name] = row
    return {"bytes": size, "sha": hashlib.sha256(image).hexdigest(), "patches": sorted(patches.items()), "rows": out}


def assignment(r):
    """A Combat Assignment: one rare or savage enemy, on Chadley's intel hub. Never itself changed."""
    if r["region"] not in OPEN_WORLD or not r["templates"] or "|" in r["templates"]:
        return False
    name = (r["territory"] + "|" + r["templates"]).lower()
    if any(w in name for w in ("demo", "quest", "test", "story")) or not any(w in name for w in ("rare", "savage")):
        return False
    return "Hub" in {x.split("/")[-1] for x in r["refs"].split(";") if x}


def report_flags(resident: Path) -> dict:
    """Camp territory -> the story flag the game sets when that camp's Combat Assignment is won.

    Resident/Hub.csv names the camp among a hub's ControlObject_Array entries and gives its WorldReportID;
    Resident/WorldReport.csv gives that report's CompleteFlag. The _Media duplicates are skipped."""
    reports = {r["Name"]: r["CompleteFlag"] for r in csv.DictReader((resident / "WorldReport.csv").open(encoding="utf-8"))}
    out = {}
    with (resident / "Hub.csv").open(encoding="utf-8") as f:
        rows = csv.reader(f); head = next(rows)
        start = head.index("ControlObject_Array"); report_at = head.index("WorldReportID")
        end = next(i for i in range(start + 1, len(head)) if not head[i].isdigit())
        for row in rows:
            if row[1].endswith("_Media") or not row[report_at]:
                continue
            flag = reports.get(row[report_at])
            for territory in row[start + 1:end]:
                if territory and flag:
                    if out.get(territory, flag) != flag:
                        raise ValueError(f"{territory}: two World Reports")
                    out[territory] = flag
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("field_root", type=Path); ap.add_argument("census", type=Path); ap.add_argument("repo", type=Path)
    ap.add_argument("--resident", type=Path, default=Path(r"D:/FF7RebirthModding/DataTableIndex/Input/Resident"),
                    help="folder with the exported Hub.csv and WorldReport.csv")
    args = ap.parse_args()
    census = list(csv.DictReader(args.census.open(encoding="utf-8")))
    flags = report_flags(args.resident)
    by_region = collections.defaultdict(list)
    for r in census:
        by_region[r["region"]].append(r)
    camps = [r for r in census if eligible(r)]
    facts = {}
    for r in census:
        for tname, s, m in zip(r["templates"].split("|"), r["sizes"].split("|"), r["moves"].split("|")):
            if tname: facts[tname] = (s, m)
    roster = collections.defaultdict(set)
    for r in camps:
        for tname in r["templates"].split("|"): roster[biome(r)].add(tname)
    tables = []; report = []; summary = {}
    for region in OPEN_WORLD:
        lay = layout(args.field_root / region / "EnemyTerritory.uasset", len(by_region[region]))
        rows = lay["rows"]
        # One place in the table where each usable enemy's name is stored, to copy at runtime.
        where = {}
        for row in rows.values():
            for k, tname in enumerate(row["templates"]):
                where.setdefault(tname, row["vector"] + 8 * k)
        unlocks = [(r["territory"], r["templates"]) for r in by_region[region] if assignment(r) and r["templates"] in where]
        region_camps = [r for r in camps if r["region"] == region and rows.get(r["territory"])]
        names = sorted({x for r in region_camps for x in roster[biome(r)]} | {u[1] for u in unlocks})
        if len(names) > 64:
            raise ValueError(f"{region}: more than 64 usable enemies")
        catalog = {n: i for i, n in enumerate(names)}
        totals = [sum(rows[r["territory"]]["max"]["values"]) for r in region_camps]
        lo, hi = min(totals), max(totals)
        targets = []
        for r in region_camps:
            row = rows[r["territory"]]
            if row["templates"] != r["templates"].split("|"):
                raise ValueError(f"census and table disagree for {r['territory']}")
            moves = r["moves"].split("|"); slots = len(moves)
            if len(row["min"]["values"]) != slots or len(row["max"]["values"]) != slots or row["min"]["vector"] is None:
                continue
            base, extra = [], []
            for m in moves:
                base.append(sorted(catalog[n] for n in roster[biome(r)] if facts[n][1] == m))
                extra.append(sorted(catalog[t] for _, t in unlocks if facts[t][1] == m))
            counts = list(range(max(lo, slots), max(hi, slots) + 1))
            original = "t:" + ".".join(str(catalog[n]) for n in row["templates"]) + "/c:" + ".".join(map(str, row["max"]["values"]))
            targets.append({"id": r["territory"], "descriptor": row["descriptor"], "template": row["vector"], "slots": slots,
                            "min": row["min"], "max": row["max"], "base": base, "extra": extra, "totals": counts, "original": original})
            report.append({"region": region, "biome": biome(r), "camp": r["territory"], "original": "|".join(row["templates"]),
                           "original_counts": "|".join(map(str, row["max"]["values"])), "totals": f"{counts[0]}-{counts[-1]}",
                           "slot_enemies": " ; ".join("|".join(names[i] for i in b) for b in base),
                           "after_assignments": " ; ".join("|".join(names[i] for i in e) for e in extra)})
        summary[region] = (len(targets), lo, hi, len(unlocks))
        tables.append({"region": region, "asset": f"/Game/DataObject/Field/{region}/EnemyTerritory.EnemyTerritory", "bytes": lay["bytes"],
                       "sha": lay["sha"], "patches": lay["patches"], "targets": targets, "names": names,
                       "catalog": [where[n] for n in names], "unlocks": [(tid, catalog[tn], flags[tid]) for tid, tn in unlocks]})
    q = lambda s: "L" + json.dumps(s, ensure_ascii=True)
    h = ["// Generated by tools/world_layout.py from the owner's own exports. Offsets, names and fingerprints only.",
         "#pragma once", "#include <cstddef>", "#include <cstdint>", "namespace reviewed {",
         "struct NamePatch {std::uint32_t offset;const wchar_t* name;};",
         "// A camp row's three lists: its enemies and its minimum and maximum counts. allowed holds, per slot, which",
         "// catalog enemies may stand there. The catalog gives one place in the table where each enemy's name is kept.",
         "struct Target {const wchar_t* id;std::uint32_t descriptor,min_descriptor,max_descriptor,template_original,min_original,max_original,slots;",
         "    const std::uint64_t* allowed;};",
         "struct Table {const wchar_t* asset;std::size_t image_bytes;const char* masked_sha256;const NamePatch* names;std::size_t name_count;",
         "    const Target* targets;std::size_t target_count;const std::uint32_t* catalog;std::size_t catalog_count;};"]
    for i, t in enumerate(tables):
        h.append(f"constexpr NamePatch names{i}[]={{" + ",".join(f"{{{o},{q(n)}}}" for o, n in t["patches"]) + "};")
        h.append(f"constexpr std::uint32_t catalog{i}[]={{" + ",".join(map(str, t["catalog"])) + "};")
        for j, c in enumerate(t["targets"]):
            masks = [sum(1 << k for k in set(b) | set(e)) for b, e in zip(c["base"], c["extra"])]
            h.append(f"constexpr std::uint64_t allowed{i}_{j}[]={{" + ",".join(f"{m}ull" for m in masks) + "};")
        h.append(f"constexpr Target targets{i}[]={{" + ",".join(
            f"{{{q(c['id'])},{c['descriptor']},{c['min']['descriptor']},{c['max']['descriptor']},{c['template']},{c['min']['vector']},{c['max']['vector']},{c['slots']},allowed{i}_{j}}}"
            for j, c in enumerate(t["targets"])) + "};")
    h.append("constexpr Table tables[]={")
    for i, t in enumerate(tables):
        h.append(f"    {{{q(t['asset'])},{t['bytes']},{json.dumps(t['sha'])},names{i},{len(t['patches'])},targets{i},{len(t['targets'])},catalog{i},{len(t['catalog'])}}},")
    h += ["};", f"constexpr std::size_t table_count={len(tables)};", "}"]
    (args.repo / "runtime/Native/src/reviewed_layout.hpp").write_text("\n".join(h) + "\n", encoding="utf-8")
    lua_list = lambda xs: "{" + ",".join(map(str, xs)) + "}"
    l = ["-- Generated by tools/world_layout.py: which camps may change and what may stand in each slot.",
         "-- Enemy numbers index the table's catalog from 0. extra slots open once their Combat Assignment is won.", "return {"]
    for t in tables:
        l.append(f"  {{asset={json.dumps(t['asset'])},region={json.dumps(t['region'])},")
        l.append("   names={" + ",".join(json.dumps(n) for n in t["names"]) + "},")
        l.append("   unlocks={" + ",".join(f"{{territory={json.dumps(a)},enemy={b},flag={json.dumps(c)}}}" for a, b, c in t["unlocks"]) + "},")
        l.append("   camps={")
        for c in t["targets"]:
            l.append(f"    {{id={json.dumps(c['id'])},base={{" + ",".join(lua_list(b) for b in c["base"]) + "},extra={" +
                     ",".join(lua_list(e) for e in c["extra"]) + f"}},totals={lua_list(c['totals'])},original={json.dumps(c['original'])}}},")
        l.append("  }},")
    l.append("}")
    (args.repo / "runtime/Scripts/world_pools.lua").write_text("\n".join(l) + "\n", encoding="utf-8")
    with (args.repo / "docs/world-pools.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["region", "biome", "camp", "original", "original_counts", "totals", "slot_enemies", "after_assignments"])
        w.writeheader(); w.writerows(report)
    for region, (n, lo, hi, u) in summary.items():
        print(f"{region}: {n} camps, totals {lo}-{hi}, {u} assignment enemies")
    print("excluded:", collections.Counter(r["region"] for r in census if r["region"] in OPEN_WORLD and not eligible(r)).most_common())


if __name__ == "__main__":
    main()
