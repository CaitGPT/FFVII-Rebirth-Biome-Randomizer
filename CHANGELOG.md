# Changelog

## 1.0.0 (not released yet)

- 210 open-world camps in seven regions change composition each time they've been fought.
- Each slot picks its own enemy from the region's camp enemies, of any size. The total is random between the region's
  smallest and largest camp. A new roll never repeats the one before.
- Any fight against a camp moves it on, unless it ends in a Game Over.
- Won Combat Assignments add their fiend to the region's pool, read from the save (so ones won before installing count) and
  from the fight.
- Empty spawn-size lists are filled from the nearest size, so bigger or smaller enemies have somewhere to stand.
- Story, quest, assignment, boss, hunt and interior encounters are excluded by a census of every table that names a camp.
- No data package: tables are changed in memory, after a fingerprint check, and read back.
- The DLL checks the loader's hash and stays off on an untested UE4SS build.
- Fixed: frame stalls from repeated object lookups (60–88 ms a tick, now under 1 ms idle), a stall when arriving in a region
  (one batched check per table), and a crash on quitting from this mod's own callback.

## 0.1.0-dev (2026-11-04, Codex)

- Four Grasslands camps, Kalm Fang or Mu with two Orcs, chosen at build time in a packed data table. Superseded by the
  runtime design; kept in [research](research/README.md).
