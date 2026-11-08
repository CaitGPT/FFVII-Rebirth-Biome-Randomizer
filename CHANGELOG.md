# Changelog

## 1.1.0 (2026-11-08)

- Shinra and bandit squads: about one roll in five, a camp in Midgar's outskirts, the Grasslands, Junon, Corel or
  Nibelheim comes back as a squad of that region's humans or machines. Per-region lists from the owner's plan, Corel
  split into desert and southern coast, chapter-select extras, at most one J-Unit Sweeper. No squads in Gongaga or
  Cosmo Canyon.
- Squad enemies use the game's always-loaded simulator templates, which point at the ordinary field enemies, from a
  reviewed list only.
- Each region uses its measured number of squad types per visit (one or two), drawn again each visit.

- Shorter stalls when camps load: only the tables of the camps that arrived are prepared, one table per tick, and a
  table found once is kept for the session rather than looked up again. Table rows are written with a guarded store
  instead of `WriteProcessMemory`, which flushed the instruction cache on every write. Before, every arrival looked up
  all seven tables by path: 350-590 ms ticks at loads. Measured on slot 17 (load, idle, one fast travel): no table
  preparation over 100 ms, and the load's game-thread stalls matched a run with the mod off (3.6 s both).
- Save records of won assignments are read once per load instead of at each camp arrival.
- Any tick over 100 ms is logged at once (at most one line a second) with how many game events ran inside it, and the
  Lua logs a `slow_step` event naming which part took the time. Other mods' queued game-thread work can run inside this
  mod's game calls, so those parts can include time that isn't ours. Before, only the five-minute maximum was logged.
- The SHA-256 provider is opened once instead of for every hash.

## 1.0.0

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
