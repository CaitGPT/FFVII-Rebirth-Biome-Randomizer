# Testing

What was tried, on what, and what came out, including what failed or wasn't reached. Raw logs, state files, screenshots and
recordings are kept outside the repository.

Setup: Steam PC game, RE-UE4SS FF7R 1.0.2 (`UE4SS.dll` SHA-256 `3f5e8d93…c0018f`), Dynamic difficulty. Saves: slot 13 (all
regions open), slot 17 (Grasslands, with some Fiend Intel done). An AI agent drove the game through our test harness.

## Offline

- `python -m pytest runtime/tests`: 32 Lua 5.4 cases for the selector, counters, state file, unlocks and the per-tick cost
  (for example, idle ticks do no lookups, table reads or story-flag reads).
- `RuntimeArgumentTests.exe`, built with the DLL: the native argument reader, 18 valid combinations plus wrong and missing types.

Offline cases use fake game objects and fake time. They don't count as game results.

## In the game, 2026-11-05 (version 1.0.0 candidates)

### Camp changes

| What | Result |
| --- | --- |
| All seven region tables recognised by their fingerprint and prepared | Passed: `table_ready` for each region on load |
| Grasslands camp fights move their camp on | Passed: five fights, each committing its camp's counter, including a Mandragora with two Orcs, three Mus, and a Venorat with a Kalm Fang |
| Mixed slots and random counts | Passed: a camp of four Kalm Fangs, and Elfadunk ×2 with Levrikon ×2 at a camp that had different enemies before |
| Any size of enemy | Passed: size-0 Mandragoras and bigger enemies spawned and fought in camps built for other sizes. The owner judged a screenshot of a large mix fine |
| A respawn outside the Grasslands comes back different | Passed once: Gongaga's `Gongaga_tomako_mob_11` went from three Kimara Bugs to the predicted three Gagighandis |
| The same in a second region (Corel or Nibelheim), two fights each | **Not reached.** The harness couldn't route to camps there (no baked navmesh on that continent yet). Left to the owner's own playtest |
| A Game Over doesn't count | Passed: the counter didn't move, and the retry met the same enemies |
| Assignment camps themselves untouched | Passed: Intel 3 and 4 fought their own three Mi and three Mandrakes |

### Combat Assignment unlocks

| What | Result |
| --- | --- |
| Winning an assignment unlocks its fiend | Passed twice on slot 17: Mandrake (`Grassland_mob_08`, a Retry) and Mi (`Grassland_swampmob_03`), each logging `assignment_unlocked` |
| Assignments won before install unlock on load | Passed: with the state cleared, loading slot 17 unlocked exactly the four whose `stfWorldReport_Finish_*` flags the harness read as true (002, 009, 017, 024) and not the two read as false (014, 029) |
| Unlocks happen before camps are prepared | Passed: the unlock events share their timestamp with `selector_ready` |

### Frames

Measured with a diagnostic build that logs every mod tick over 50 ms and times each part of the Lua step.

| When | Our cost |
| --- | --- |
| Loading a save or fast travelling | Up to about 600 ms in total while the camp tables are prepared. Matched to timestamped OBS frames: all of it while the loading screen was still black |
| Walking 800 m across the Grasslands | No tick over 50 ms |
| Standing in the field, only this mod installed | No step over 15 ms in two minutes |
| With the test harness's own mods loaded | Occasional 40–114 ms in the call that asks for the player. Not seen without the harness, so players won't have it |

1.0.1, measured 2026-11-08 on slot 17 with the test harness loaded. Each run loaded the save, stood 2 minutes, fast travelled
to Thresher Waterwheel and stood 1 minute. Stalls are the OBS monitor's game-thread measurement over the load.

| Build | Load stalls | Our slow ticks |
| --- | --- | --- |
| Runtime off | 3.6 s, 12 over 100 ms, 1 over 250 ms | none |
| First 1.0.1 candidate | 4.8 s, 16 over 100 ms, 3 over 250 ms | Grasslands table 586 ms; Midgar 103 ms (31 ms lookup, 66 ms writing) |
| 1.0.1 | 3.6 s, 9 over 100 ms, 1 over 250 ms | No table preparation over 100 ms |

The other slow ticks, in every build, were inside the single call that asks for the player, with up to 2,400 of other
mods' game events run inside it (the harness's queued work). With the runtime off, the same work runs elsewhere: fast
travel showed no extra stalls with the mod on. Players without the harness don't have it.

### Install, remove, quit

| What | Result |
| --- | --- |
| Release DLL `65287f2f…` with only this mod enabled | Loaded the latest save, tables ready, quit cleanly in 4 s, no crash report |
| Mod switched off | Game loads into the field normally, nothing from the mod in the log, quit cleanly |
| The public loader download | The `UE4SS.dll` in RE-UE4SS FF7R 1.0.2 from Nexus is byte-identical to the tested one |
| A loader that isn't the tested one | Not run in the game. The DLL hashes `UE4SS.dll` before registering anything and stays off with an `inactive` line on a mismatch |
| Fatal error on quitting | Seen only with the harness's telemetry mods loaded, with or without this mod. Not seen with this mod alone |

### Earlier, by Codex (2026-11-04)

The first four-camp version passed clear-to-respawn in both directions, restart persistence and living-group streaming at camp
05, and found the transient Lua-state failure that led to the persistent dispatcher. Those notes are in
[the research folder](../research/README.md).

## Owner playtest, 2026-11-06

The owner reports also playtesting the mod in Corel. This is additional human playtesting, separate from the
agent-run results above. Individual camps, fight counts and respawn outcomes were not recorded in that report;
it does not mark the earlier two-fight agent test as completed.

### Squads (in progress, 2026-11-08)

Live on slot 13 (chapter select, Chapter 12) and slot 17, with a test config that made every camp in a squad region a
squad. Nothing was saved.

| What | Result |
| --- | --- |
| Save gates | `squad_gates` read Chapter 12 and chapter select released on slot 13 |
| Grasslands (experiment build) | Security Officer, Slug-Ray and Bandit squads spawned, looked like the field enemies, fought and counted; an in-game reload restored and re-prepared without a crash |
| Junon | J-Unit Sweeper squads (one per squad) fought and counted twice; Junon Elite Security Officers spawned (chapter-select gate). The game spawned the Sweeper as its Junon variant |
| Corel desert | Bandits and Thugs spawned, but only two enemy types of the eight in the pool |
| Corel southern coast | Its squad camps spawned nothing, after the desert's two types |
| Nibelheim | Security Officer squads spawned |

The limit: a region spawns at most two squad enemy types it doesn't already load for itself. Slots naming a third type
spawn nothing (no crash, no fault). Shown by the desert: four types requested, two spawned (other members of the same
camps missing); a different two on another run; one type requested, it spawned everywhere. The empty southern coast in
that run was mostly where we stood: from Clamshell Beach, below the cliff, its camps hadn't spawned yet.

So squads now share a two-type budget among the units loaded at once (a region, or a Corel half). Measured the same
evening on the 2026-11-05 Proof of Concept backup (chapter select) in test slot 10, every camp a squad, nothing saved:

| Unit | Types drawn | Result |
| --- | --- | --- |
| Corel desert | Bandit (Scimitar) | All 14 camps in range full |
| Corel southern coast | Slug-Ray | All 8 camps full, seen from the clifftop |
| Junon (alone) | Junon Elite Security Officer, Type G Slug-Ray | Both types in 13 camps, some camps holding both |
| Nibelheim (alone) | Security Officer, Flametrooper | Security Officers in the three camps in range; no Flametrooper seen (its camps were further out) |

Leaving each region released its budget (`level_left` restored every camp). No faults; every slow tick was inside the
call that asks for the player, with the test harness loaded.
