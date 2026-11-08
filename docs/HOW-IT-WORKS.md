# How it works

The mod never adds enemies, camps or files to the game. It changes which enemies the game's own camp tables list for a camp,
in memory, while the game runs, and lets the game spawn them as usual. For the story of how it got this way, see
[HOW-WE-BUILT-IT.md](HOW-WE-BUILT-IT.md).

## The camp tables

Each open-world region has an `EnemyTerritory` table (`/Game/DataObject/Field/<region>/EnemyTerritory`). Each row is a camp:
which enemy templates it uses, how many of each (a minimum and a maximum, one byte per slot), their levels, where it spawns and
when it respawns. The game keeps these tables frozen in memory. A list inside a row isn't stored inline. It's a 16-byte
descriptor holding a relative pointer (`(target - descriptor) * 2 | 1`) and a length, and several rows often share one list.

So the mod never edits a list. For a camp it changes, it builds its own small lists (eight bytes per enemy name, one byte per
count), allocated once and kept for the whole session, and points that row's three descriptors at them: enemies, minimum counts
and maximum counts. Levels, positions, rewards and timers are untouched, which is why a swapped-in enemy gets the camp's level.

## Which camps, and what can stand in them

Nothing is decided at runtime that wasn't reviewed offline. Two generators read the owner's exports of the game's tables:

- `tools/census.py` lists every territory row in the seven regions, with its enemies, counts, sizes, and every other table
  that mentions it.
- `tools/world_layout.py` picks the eligible camps: ordinary open-world camps, not named by any quest, story reset, scripted
  state change or event, and not an assignment, boss, hunt or interior. That's 210 camps. For each region it writes the
  enemies its camps use (the pool), the smallest and largest camp totals, the assignment fiends that can be unlocked, and the
  World Report flag that records each assignment's win.

It writes `runtime/Scripts/world_pools.lua` (the pools) and `runtime/Native/src/reviewed_layout.hpp` (table sizes, descriptor
offsets and fingerprints). Neither contains game data beyond names and offsets.

## Checking before writing

Before any write, the native part checks the live table against what was reviewed: the whole table image is hashed with its
name fields masked and compared with the reviewed fingerprint, and every name is checked separately. Every row the mod may
change must point either at the game's own list or at one of the mod's lists. A table that doesn't match is left alone.

All of a table's changes go through in one batch: one full check before, the writes, one full check after. If the read-back
doesn't match what was written, a latch stops all further writes for the session.

## Room to stand

Each camp has its own spawn points, kept in separate lists by enemy size (`TerritoryGroundSpawnPoints_S`, `_M`, `_L`, `_2L`,
`_3L`, `_4L`, and flying ones). Camps usually fill only the sizes their own enemies need, and asking for a size with no points
crashes the game. So when a camp's spawn actor loads, the mod fills each empty list with a copy of the nearest size that has
points.

Spawn actors live in levels named `*_World_Navigation_Mod_ServerBuild`. The mod watches the world's list of loaded levels and
reacts when one appears or goes. A camp only gets a new composition once its spawn lists are filled. When a level unloads,
its tables go back to the game's own lists first, and they're set again when the level returns.

## Choosing a composition

A camp's composition depends only on the seed, the camp and that camp's counter. Each slot's enemy and the camp's total come from
SHA-256 of `sha256-respawn-v1`, the seed, a salt (`<camp>#<slot>` for an enemy, `<camp>#n` for the total) and the counter, all
length-prefixed. The first eight hex digits modulo the pool size pick from the pool. The total is spread over the slots as
evenly as possible.

If a roll matches the camp's previous composition (the game's own one, for the first roll), it rolls again with `~1`, `~2`
and so on added to the salts. Each camp's sequence is worked out once and kept until an unlock changes the pools.

## Counting fights

During a battle the mod reads the battle's enemy roster. Field enemies are named `<template>@<territory>`, so each one names
its camp. When the battle ends, every camp that was in it moves its counter on by one, unless the party is wiped out, which is
a Game Over. Winning and running away both count. The new composition is set straight away for the camp's next respawn; the
game's own timer and streaming decide when that is.

## Combat Assignment unlocks

An assignment camp is never changed itself. Its fiend joins its region's pools, for slots of the same movement type, once the
assignment has been won. The mod knows that two ways:

- The save's record: when a save loads, before any camp is set up, and a few seconds after an assignment fight, it reads each
  assignment's `stfWorldReport_Finish_*` story flag through `EndDataBaseAPI:IsStoryFlag`. This counts assignments won before the
  mod was installed. The generator gets each flag from the intel hub table (`Hub`), which names the camp and its World Report,
  and from that report's `CompleteFlag`.
- The fight: the assignment's fiend was in a battle that ended without a Game Over, and is gone from the field afterwards.

Unlocks are kept in the state file, so they belong to the install, not the save.

## Squads

Squad enemies come from the game's always-loaded Resident `EnemyTerritoryMob` table: 264 combat simulator templates
(`mobcolvr_...`), each pointing at the ordinary field enemy's own spec. A composition names one as `r<n>`, an index into
the reviewed list in `Native/src/resident_templates.hpp`; the native writer looks the name up without creating it and
refuses anything else. `Scripts/squads.lua` holds which squads each region (or Corel half) may use, and when.

A region spawns only a measured number of squad enemy types it doesn't load itself (`squads.type_budget`): past it, the
first types asked for spawn and further ones spawn nothing for the whole visit. When a table is prepared, its units draw
that many types from their pool, seeded by a visit counter kept in the state file, and their squads use only those.
About one roll in five makes a camp a squad. The save's chapter (`GetChapterProgress`) and chapter select
(`stfComn_Release_ChapterSelect`) gate the rest.

## State and timing

`%LOCALAPPDATA%\FFVIIRebirthBiomeRandomizer\state-v1.json` holds the seed, each camp's counter and the unlocked fiends. It's
written on a background thread (atomically, keeping the previous file), so a fight ending never waits for the disk.

The Lua runs from a small native dispatcher on the game thread every 100 ms, on the mod's one long-lived Lua state. Work is only
done when something changes. Idle ticks don't look objects up or read tables. Objects are found once and cached. When the game
quits, the dispatcher stops at the first quit event, before the world is torn down.

When spawn levels arrive, the native poll names the camps that came with them. Only those camps' tables are prepared, at
most one table a tick, and a table found once is kept for its later camps and for putting it back when its level leaves.
A tick over 100 ms is logged at once, and the Lua logs a `slow_step` event that names which part took the time. A part
that is a single game call can also hold other mods' queued game-thread work, which the engine runs inside it.

The DLL checks the SHA-256 of the running `UE4SS.dll` before registering anything, because a C++ mod is tied to the exact loader
build it was compiled against. On any other build the mod stays off and says so in `UE4SS.log`.
