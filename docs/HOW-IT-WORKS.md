# How it works

## Reviewed scope

The input territory table contains forty-four rows. Four are selected explicitly: `Grassland_mob_05`, `Grassland_mob_23`, `Grassland_mob_29` and `Grassland_mob_30`. Each originally has one Kalm Fang and two Orcs, levels `[15,15]`, counts `[1,2]`, and field AI `[1,1]`. The alternate species list comes from ordinary native donor18 (Mu2+Orc2); only the species list is used, so each target retains Mu1+Orc2.

The original regional mob table maps templates to BattleCharaSpec, and the resident BattleCharaSpec table maps those to CharaSpec. All three pool enemies have exact PhysiqueSize1 and MoveType0. The build binds all four original asset hashes and validates these mappings, HPDirect0 and exact HP coefficients. A target-population-weighted HP coefficient budget is630 for Kalm1+Orc2 and500 for Mu1+Orc2 (79.4%). This bounds one dimension of difficulty; it is not an equal-difficulty claim.

Mandragora has size0 and is excluded, including its native territory02. The prior Mandragora design crashed; the matched-size Mu replacement at05 spawned correctly and completed in game. See [the compatibility investigation](COMPATIBILITY.md). Matching categories establishes candidates, not universal swap acceptance.

The story/reset-linked territory01 and its Media variant, swamp, rare, hunt, quest and boss encounters are excluded. Neither enemy names nor a region prefix authorizes a target. Structural source checks and the exact allowlist constrain the change; map scripts and encounter completion still require native evidence.

## Selection

The algorithm hashes a canonical UTF-8 JSON array containing the algorithm ID, seed string, pool ID and target ID. The full SHA-256 integer modulo the number of sorted donor IDs chooses the donor. Sorting makes selection independent of dictionary and catalog list order. There is no global RNG state, current-time seed or dependency on route traversal order.

The builder changes only `MobTemplateList_Array` in selected rows whose choice differs from vanilla. It preserves all other properties and every unselected row. It adds no rows and leaves EnemyTerritoryMob and all other assets out of the package. Selecting a vanilla composition is valid and is reported as an unchanged choice.

## Verification

The builder first verifies original binary SHA-256 hashes, exports the tables using DataBuilder's long CSV format, and checks each reviewed target and donor's structural constraints, count budgets and complete character mapping. DataBuilder edits and rereads its own result. A separate Python comparison rereads the output CSV and requires the exact expected change in every row and property. Original input hashes are checked again before success.

The audit records the algorithm, seed, catalog and input hashes, per-target selections, modified asset hash and complete package hashes. Every IoStore block is decompressed and the packed asset is compared with the independently verified table. The final archive uses native Oodle compression, version-2 TOC fields, SHA-1 metadata and a valid Rebirth-shaped empty container header. The existing game's package-store metadata describes this existing asset. Generated packages remain labelled `packed_unvalidated` until a separate native test supplies evidence. The [packaging investigation](PACKAGING-INVESTIGATION.md) records the failed controls and why copying arbitrary UCAS prefix bytes was removed.

All choices remain stable through save/load and respawn because the mapping is baked into the package. This is not per-spawn or per-visit randomisation. No runtime code writes data tables or save files.

## Limits

Only one small Grasslands pool has been researched. Swamp ecology, flying enemies, large enemies, rare spawns, progression scaling, authored fights and other regions are excluded. Level and count matching bound the initial change but do not establish equal difficulty. Collision, AI, streaming and encounter completion require recorded native validation. A fixture pass cannot satisfy these cases.
