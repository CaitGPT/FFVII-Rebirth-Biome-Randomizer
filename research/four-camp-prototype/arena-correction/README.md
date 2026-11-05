# Experimental cross-category arena correction

This is separate from the default seeded Kalm Fang/Mu package. It demonstrates a scoped Kalm Fang-category arena supporting Mandragora's original category. It is not an all-enemy interchangeability system.

## Native result

Grassland_mob_05 originally has12 medium ground spawn transforms and zero small ones. Mandragora is category0 (small); Kalm Fang/Mu/Orc are1 (medium). The companion copies this arena's existing12 medium transforms to its empty small list, then reads back every component. An independent count comparison over69 server-build actors found only05's small list changed.

Mandragora1+Orc2 then spawned and entered native combat. That attempt ended in party defeat on Hard. At the owner's request, a separate single-enemy diagnostic retained one level15 Mandragora and removed the two Orc groups from the camp's logical lists. The native fight completed on Hard: the game reported Mandragora defeated,188gil,1524EXP/3AP and a pearl ginger root, then returned to the field. Cloud remained901HP; no healing/revival command was sent to him. The original nearby save was preserved.

This verifies spawning, active combat and one-enemy encounter completion with the scoped correction. It does not establish balance or completion of every mixed group or support for other arenas/categories.

## Companion

`Scripts/main.lua` is the exact runtime experiment that passed the test. It targets one exact server-build actor path, requires the reviewed medium count12 and an empty small list, validates finite transforms/positive scales and checks complete readback. It never creates enemies, changes character definitions, changes difficulty or writes saves. An uncertain write stops further attempts. It resolves actors afresh instead of retaining UObject wrappers across unloads.

The experiment used UE4SS3.0.1 beta c0a8d4c. Install this optional script as a separate UE4SS mod only with its matching diagnostic package. The ordinary seeded package needs no companion. Preserve existing activation and package files before testing; never mix triplets or overwrite another mod's files.

## Reproduce the isolated package

Use your own hash-verified original exports and the normal build tools. First build a normal package to obtain the existing territory chunk identity/directory. Build the included three-enemy spec through DataBuilder:

```powershell
dotnet tools/DataBuilder/bin/Release/net8.0/TrainingDummy.DataBuilder.dll build experimental/arena-correction/mandragora-three-enemy.spec.json <original-export-root> <diagnostic-staging-root>
python experimental/arena-correction/build_single_enemy.py --config tools/build-config.local.json --source-asset <diagnostic-staging-root>/End/Content/DataObject/Field/1200-GRASA/EnemyTerritory.uasset --template-build <normal-build-directory> --output <new-diagnostic-build-directory>
```

The helper binds the reviewed source hash, locates fields from the frozen table's metadata and changes only the five camp05 array lengths from2 to1. It retains capacity/backing storage and the24160-byte package size, preserving the original package-store contract. DataBuilder independently exports every field before/after, and retoc independently decodes the final packed asset. No binaries, original exports or codec DLLs are included here. Its audit explicitly says `release_eligible:false`.

The five synthetic guard/readback tests require the optional `lupa` developer package and use its Lua5.4 runtime:

```powershell
python -m unittest discover -s experimental/arena-correction -p "test_*.py" -v
```

They are not native gameplay evidence. Retain failed tests and full recordings. Do not substitute this one-enemy diagnostic for the default encounter populations in a player release.
