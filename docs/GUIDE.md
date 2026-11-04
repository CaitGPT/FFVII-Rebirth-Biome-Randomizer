# Player and build guide

This is an unreleased prototype. Keep your original saves backed up. Native placement, completion and balance testing must pass before a player release.

## Requirements

- The supported PC game's own raw FModel exports, containing `End/Content/DataObject/Field/1200-GRASA/EnemyTerritory.uasset` and `EnemyTerritoryMob.uasset`.
- Python 3.10 or later and the .NET 8 SDK for building. The Python tools use only the standard library; DataBuilder has no NuGet dependencies.
- UnrealReZen for packing, and the game installation's IoStore files.

The builder checks both original table hashes against the reviewed catalog and stops on an unreviewed game version. Do not remove that check to force a different version to work. Re-export and inspect the data instead.

## Generate a seed

Copy `tools/build-config.example.json` to `tools/build-config.local.json` and set your own export, game and packager paths. The local file is ignored by Git. Run from the repository root:

```powershell
python tools/build.py --config tools/build-config.local.json --seed 44
```

This builds the source reader, exports read-only input data, and creates a plan and audit under `build/seed-<unique suffix>/`. It does not edit or install game assets. Inspect `audit.json` for each encounter's original and selected composition.

```powershell
python tools/build.py --config tools/build-config.local.json --seed 44 --execute --pack
```

This writes and independently verifies the modified table, then packs the package triplet. `--execute` without `--pack` writes only the verified table. To produce the smallest diagnostic build, add `--only Grassland_mob_05`. The option refuses targets outside the explicit allowlist.

A seed is a string: `44` and `044` are different seeds. The same seed, catalog and algorithm produce the same selected encounters. Different seeds can sometimes select the same composition at a particular encounter; there are two choices per encounter.

## Install and remove a tested package

Close the game first. Back up any existing complete `BiomeRandomizer_P.pak`, `.ucas` and `.utoc` triplet and compare SHA-256 hashes. Copy the new complete triplet from the selected build's `package/` directory into `End/Content/Paks/~mods/`. Verify the installed hashes against `audit.json` before launching. Do not mix files from different builds.

To remove the prototype, close the game, retain a backup, and remove only its three named files. Restore an earlier package only from its own verified complete triplet. Other mods are independent and should remain installed.

The encounter mapping is part of the installed package. Restart the game after changing seeds. There is no runtime seed setting, UI, Lua component, or UE4SS dependency for this mod itself.

## Compatibility

This package replaces `DataObject/Field/1200-GRASA/EnemyTerritory.uasset`. Another mod replacing that asset conflicts even if it edits different rows. Load order does not merge tables. The installed Training Dummy mod replaces Resident tables instead; that asset-path comparison is not a complete native compatibility test.

Enemy level and count preservation does not make the two species identical in difficulty. The initial pool deliberately changes only one small ground enemy and leaves the two Orcs fixed. Story progression, other regions and higher-level variants are outside this prototype's scope.
