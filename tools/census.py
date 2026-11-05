"""World census of enemy territories, from CSV exports of the owner's own game tables.

usage: census.py <DataTableIndex/Input> <out.csv>

For every region's EnemyTerritory table, writes one row per territory: what it spawns, those enemies'
physique size and movement type, and anything marking it as more than an ordinary field camp, including
references from other tables. No game data goes into the repo beyond these derived facts.
"""
import csv, re, sys, collections
from pathlib import Path

csv.field_size_limit(10_000_000)
ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2])


def rows(path):
    """Yield dicts keyed by header, gathering array columns (Name_Array,1,2,...) into lists."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for raw in reader:
            out = {}; current = None
            for name, value in zip(header, raw):
                if name.endswith("_Array"):
                    current = name; out[name] = [value]
                elif name.isdigit() and current:
                    out[current].append(value)
                else:
                    current = None; out[name] = value
            yield out


def clean(values):
    return [v.strip() for v in values if v.strip() and not v.strip().startswith("0    |")]


def resident(name):
    for p in [ROOT / "Resident" / f"{name}.csv", *ROOT.glob(f"Resident/**/{name}.csv")]:
        if p.exists():
            return p


chara = {r["Name"]: r for r in rows(resident("CharaSpec"))}
battle_global = {r["Name"]: r for r in rows(resident("BattleCharaSpec"))}
battle_field = {}
for p in ROOT.glob("Field/*/BattleCharaSpec.csv"):
    for r in rows(p):
        battle_field.setdefault(r["Name"], r)
mobs_common = {}
common = ROOT / "Field/0000-COMON/EnemyTerritoryMob.csv"
if common.exists():
    mobs_common = {r["Name"]: r for r in rows(common)}


def spec_of(template, mobs):
    mob = mobs.get(template) or mobs_common.get(template)
    if not mob:
        return None
    bspec = mob.get("BattleCharaSpecID", "")
    b = battle_global.get(bspec) or battle_field.get(bspec)
    cname = (b or {}).get("CharaSpec") or (b or {}).get("CharaSpecID") or ""
    c = chara.get(cname) or chara.get(bspec) or chara.get("CharaSpec_" + bspec)
    return {"battle": bspec, "size": (c or {}).get("PhysiqueSize", "?"), "move": (c or {}).get("MoveType", "?"),
            "hp": (b or {}).get("HPCoefficient", (b or {}).get("HP", "?"))}


# Every territory name referenced from any table other than its own region's territory tables.
territories = {}
regions = sorted(p.parent for p in ROOT.glob("Field/*/EnemyTerritory.csv"))
for region in regions:
    for r in rows(region / "EnemyTerritory.csv"):
        territories[r["Name"]] = region.name
pattern = re.compile("|".join(sorted(map(re.escape, territories), key=len, reverse=True)) + r"(?![A-Za-z0-9_])")
refs = collections.defaultdict(set)
for p in ROOT.rglob("*.csv"):
    if p.name in ("EnemyTerritory.csv", "EnemyTerritoryLevel.csv", "EnemyTerritoryGroup.csv"):
        continue
    text = p.read_text(encoding="utf-8-sig", errors="replace")
    for m in set(pattern.findall(text)):
        refs[m].add(str(p.relative_to(ROOT).with_suffix("")).replace("\\", "/"))

fields = ["region", "territory", "kind", "type", "respawn", "templates", "pop_min", "pop_max", "levels", "battles", "sizes", "moves", "hp",
          "waves", "external", "blueprint", "force_finish", "rare", "refs"]
with OUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fields); w.writeheader()
    for region in regions:
        mob_path = region / "EnemyTerritoryMob.csv"
        mobs = {r["Name"]: r for r in rows(mob_path)} if mob_path.exists() else {}
        for r in rows(region / "EnemyTerritory.csv"):
            name = r["Name"]
            templates = clean(r.get("MobTemplateList_Array", []))
            specs = [spec_of(t, mobs) for t in templates]
            kind = "mob" if re.search(r"_mob_\d", name, re.I) else "other"
            for word, label in (("rare", "rare"), ("boss", "boss"), ("hunt", "hunt"), ("story", "story"), ("quest", "quest"), ("media", "media"), ("event", "event"), ("sub", "sub")):
                if word in name.lower():
                    kind = label
            w.writerow({"region": region.name, "territory": name, "kind": kind, "type": r.get("TerritoryType", ""), "respawn": r.get("RespawnTimer", ""),
                        "templates": "|".join(templates),
                        "pop_min": "|".join(clean(r.get("MinPopList_Array", []))), "pop_max": "|".join(clean(r.get("MaxPopList_Array", []))),
                        "levels": "|".join(clean(r.get("MobLevelList_Array", []))),
                        "battles": "|".join((s or {}).get("battle", "?") for s in specs),
                        "sizes": "|".join((s or {}).get("size", "?") for s in specs), "moves": "|".join((s or {}).get("move", "?") for s in specs),
                        "hp": "|".join(str((s or {}).get("hp", "?")) for s in specs),
                        "waves": len(clean(r.get("WaveMobTemplateList_Array", []))), "external": len(clean(r.get("ExternalEnemiesList_Array", []))),
                        "blueprint": r.get("BattleSceneBluePrint", "").strip(), "force_finish": len(clean(r.get("ForceFinishBattleOnKill_Array", []))),
                        "rare": int(any("rare" in t.lower() for t in templates)),
                        "refs": ";".join(sorted(refs.get(name, ())))})
print("wrote", OUT)
