# Player and build guide

This is an unreleased runtime prototype. Final compatibility and removal acceptance are in progress; see [release QA](RELEASE-QA.md). The current pool covers four ordinary level-15 Grasslands camps, not the whole world.

## Runtime requirements

The tested native module uses UE4SS 3.0.1 Beta #0, commit `c0a8d4cb259dccb8d7b58aec8b89e51c97222f9b`. Its C++ ABI must match the loader. A newer UE4SS build is not automatically compatible. The reviewed game table must pass the full runtime fingerprint check; unknown tables disable substitution.

The public Rebirth loader is [RE-UE4SS FF7R](https://www.nexusmods.com/finalfantasy7rebirth/mods/267?tab=files). It offers several game-version variants. The exact correspondence between these downloads and our tested local loader remains to be verified before release. Do not assume that an arbitrary variant is compatible. We do not redistribute the loader.

## Install

Close the game. Back up existing UE4SS configuration and any existing `BiomeRandomizerRuntime` folder. Retain normal save backups. The mod belongs beneath `End/Binaries/Win64/ue4ss/Mods/`:

```text
BiomeRandomizerRuntime/
  dlls/main.dll
  Scripts/main.lua
  Scripts/automatic.lua
  Scripts/lifecycle.lua
  Scripts/state_store.lua
  Scripts/biome_json.lua
  Scripts/config.lua
```

Enable `BiomeRandomizerRuntime : 1` once in the existing `mods.txt`, preserving other entries. Compare installed hashes with the release manifest. No game assets, developer harness, request files or modified saves are required.

Move our earlier `BiomeRandomizer_P.pak`, `.ucas` and `.utoc` triplet out of the active Paks directory to a verified backup first. That fixed-composition experiment conflicts with the runtime's original-table check. Never mix it with the runtime package.

## Seed and respawns

The default `Scripts/config.lua` is:

```lua
return { enabled=true, seed='auto' }
```

`auto` creates a random seed once and reuses it. To reproduce a sequence, set a chosen nonempty string, for example `'13'`, while the game is closed. A different explicit seed starts a new sequence. `'13'` and `'013'` differ. There is no in-game settings menu.

State is separate from game saves: `%LOCALAPPDATA%/FFVIIRebirthBiomeRandomizer/state-v1.json`, with a previous-state backup. Preserve both when updating. Removing state deliberately resets the sequence; back it up first. Corrupt or incompatible state disables operation instead of silently resetting progress.

The seed, camp ID and complete-clear counter select Kalm Fang/two Orcs or Mu/two Orcs. All three exact members must be verified dead and the party alive outside battle before a counter advances. The selection is ready for the game's next normal respawn. The original 180-second timer and normal streaming rules still apply. Revisit, load, defeat, retreat and unloading a living group do not advance a counter. The next random choice can repeat the current composition. State is global to this installation, not tied to one save slot.

## Remove and diagnose

Close the game, retain manifest/state backups, disable the single `BiomeRandomizerRuntime` entry and remove only its folder. Runtime changes vanish with the process. Keep UE4SS and other mods installed. The optional state folder can remain for reuse. Native removal acceptance is recorded separately in the QA report.

Search `UE4SS.log` for `[BiomeRandomizerRuntime]`. `selector_ready`, `reference_ready`, `group_acquired`, `clear_committed` and `spawn_observed` describe different stages: a table write does not prove a spawn. `automatic_disabled` or `automatic stopped` means substitution has stopped. Preserve the log, version, seed and manifest with a bug report.

Another mod editing regional EnemyTerritory data or its references is incompatible. The fingerprint does not validate other mods' enemy-stat, AI, movement, arena or reward changes. See [compatibility](COMPATIBILITY.md). Equal counts and levels do not establish equal difficulty.

## Build from source

Runtime source is in `runtime/Native` and `runtime/Scripts`. [The pinned build recipe](../runtime/BUILDING.md) records exact SDK commits, authenticated UEPseudo access, import-library generation from the tested loader and parameterized build commands. The repaired source compiled through that recipe with a newly generated import library. It never installs files or starts the game. Exact public-loader download correspondence remains a separate release prerequisite.

Run the Python tests in `runtime/tests` with Lua 5.4 and the compiled `RuntimeArgumentTests` executable. Synthetic results do not pass native acceptance cases.

## Legacy fixed-package research

The earlier package builder selects compositions at build time and does not implement reroll-on-respawn. Its seed algorithm differs from the runtime. It remains available for controlled comparisons.

It requires the game's raw FModel exports at the four paths in `data/pools.json`, Python 3.10+, .NET 8, UnrealReZen, the owner's Oodle library and the game's IoStore files. Proprietary inputs are excluded from source/releases. Copy `tools/build-config.example.json` to ignored `tools/build-config.local.json` and configure local paths. From the repository root:

```powershell
python tools/build.py --config tools/build-config.local.json --seed 44
python tools/build.py --config tools/build-config.local.json --seed 44 --execute --pack
```

The first command creates a read-only plan/audit. The second writes and independently verifies a package. Only the complete triplet in the audited `package_directory` is installable. Keep intermediate outputs for diagnosis. `--only Grassland_mob_05` restricts the experiment to that allowlisted camp. Never install this research package alongside the runtime.
