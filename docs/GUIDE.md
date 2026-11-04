# Player and build guide

This is an unreleased prototype. Keep your original saves backed up. Native placement, completion and balance testing must pass before a player release.

## Requirements

- The supported PC game's own raw FModel exports: regional `EnemyTerritory` and `EnemyTerritoryMob`, plus resident `BattleCharaSpec` and `CharaSpec`, at the four paths recorded in `data/pools.json` under `End/Content/`.
- Python 3.10 or later and the .NET 8 SDK for building. The Python tools use only the standard library; DataBuilder has no NuGet dependencies.
- UnrealReZen for initial archive identity/directory construction, the owner's installed Oodle library for compression, and the game installation's IoStore files. The proprietary DLL is not included in this source repository.

The builder checks all four original table hashes against the reviewed catalog and stops on an unreviewed game version. Do not remove that check to force a different version to work. Re-export and inspect the data instead.

## Generate a seed

Copy `tools/build-config.example.json` to `tools/build-config.local.json` and set your own export, game and tool paths. `oodle` points to the installed codec DLL; if omitted, the builder looks beside UnrealReZen for `oo2core_9_win64.dll`. Set `build_root` on the game's volume so the builder can create its vanilla-only archive view without copying the game's archives. The local file is ignored by Git. Run from the repository root:

```powershell
python tools/build.py --config tools/build-config.local.json --seed 44
```

This builds the source reader, exports read-only input data, and creates a plan and audit under `build/seed-<unique suffix>/`. It does not edit or install game assets. Inspect `audit.json` for each encounter's original and selected composition.

```powershell
python tools/build.py --config tools/build-config.local.json --seed 44 --execute --pack
```

This writes and independently verifies the modified table, then packs and verifies the package triplet. The final files are in the directory named by `package_directory` in `audit.json` (currently `package-corrected/`). Intermediate packager output is retained for diagnosis and is not the installable result. `--execute` without `--pack` writes only the verified table. To produce the smallest diagnostic build, add `--only Grassland_mob_05`. The option refuses targets outside the explicit allowlist.

A seed is a string: `44` and `044` are different seeds. The same seed, catalog and algorithm produce the same selected encounters. Different seeds can sometimes select the same composition at a particular encounter; there are two choices per encounter.

For algorithmv2 and the reviewed catalog, seed3 selects Mu1+Orc2 at all four targets; seed6 selects the original Kalm Fang1+Orc2 at all four. Seed44 selects Mu at05/23 and Kalm Fang at29/30. These are build-plan expectations, not native acceptance receipts. Mandragora is currently excluded; see [the cross-category investigation](COMPATIBILITY.md).

## Install and remove a tested package

Close the game first. Back up any existing complete `BiomeRandomizer_P.pak`, `.ucas` and `.utoc` triplet and compare SHA-256 hashes. Copy the new complete triplet from the selected build's audited `package_directory` into `End/Content/Paks/~mods/`. Verify the installed hashes against `audit.json` before launching. Do not mix files from different builds or install intermediate output.

To remove the prototype, close the game, retain a backup, and remove only its three named files. Restore an earlier package only from its own verified complete triplet. Other mods are independent and should remain installed.

The encounter mapping is part of the installed package. Restart the game after changing seeds. There is no runtime seed setting, UI, Lua component, or UE4SS dependency for this mod itself.

## Compatibility

This package replaces `DataObject/Field/1200-GRASA/EnemyTerritory.uasset`. Another mod replacing that asset conflicts even if it edits different rows. Load order does not merge tables. The installed Training Dummy mod replaces Resident tables instead; that asset-path comparison is not a complete native compatibility test.

Enemy level and count preservation does not make the two species identical in difficulty. The initial pool deliberately changes only one small ground enemy and leaves the two Orcs fixed. Story progression, other regions and higher-level variants are outside this prototype's scope.
