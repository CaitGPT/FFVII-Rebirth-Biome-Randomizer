# How it works

## Reviewed scope

The input table contains forty-four rows. Five are explicitly selected: `Grassland_mob_02`, `Grassland_mob_05`, `Grassland_mob_23`, `Grassland_mob_29` and `Grassland_mob_30`. The two donor compositions come from the first two of those rows. All have levels `[15,15]`, minimum and maximum counts `[1,2]`, and the same field AI. A Mandragora or Kalm Fang occupies the first entry, and Orcs occupy the second.

The mapping between mob IDs and character specs is checked in the original regional `EnemyTerritoryMob` table. Neither enemy names alone nor the region prefix authorizes an encounter. The source table hashes and the exact allowlist establish the reviewed input version and scope. Native tests must establish which physical arena each target uses and whether the swap behaves correctly there.

The story/reset-linked `Grassland_mob_01` and its Media variant are deliberately excluded. A search of all local indexed CSV tables found exact references for the five candidate IDs only in the regional EnemyTerritory table. This is useful classification evidence, but it is not proof about every map script or hard-coded game behavior. Protected encounter regression testing remains required.

## Selection

The algorithm hashes a canonical UTF-8 JSON array containing the algorithm ID, seed string, pool ID and target ID. The full SHA-256 integer modulo the number of sorted donor IDs chooses the donor. Sorting makes selection independent of dictionary and catalog list order. There is no global RNG state, current-time seed or dependency on route traversal order.

The builder changes only `MobTemplateList_Array` in selected rows whose choice differs from vanilla. It preserves all other properties and every unselected row. It adds no rows and leaves EnemyTerritoryMob and all other assets out of the package. Selecting a vanilla composition is valid and is reported as an unchanged choice.

## Verification

The builder first verifies original binary SHA-256 hashes, exports the tables using DataBuilder's long CSV format, and checks each reviewed target and donor's structural constraints and mob-to-spec references. DataBuilder edits and rereads its own result. A separate Python comparison rereads the output CSV and requires the exact expected change in every row and property. Original input hashes are checked again before success.

The audit records the algorithm, seed, catalog and input hashes, per-target selections, modified asset hash and complete package hashes. Every IoStore block is decompressed and the packed asset is compared with the independently verified table. The selected package-store entry comes from the actual vanilla container and is written in Rebirth's legacy layout. Generated packages are labelled `packed_unvalidated` until a separate native test supplies evidence. The [packaging investigation](PACKAGING-INVESTIGATION.md) records why copying arbitrary UCAS prefix bytes was removed.

All choices remain stable through save/load and respawn because the mapping is baked into the package. This is not per-spawn or per-visit randomisation. No runtime code writes data tables or save files.

## Limits

Only one small Grasslands pool has been researched. Swamp ecology, flying enemies, large enemies, rare spawns, progression scaling, authored fights and other regions are excluded. Level and count matching bound the initial change but do not establish equal difficulty. Collision, AI, streaming and encounter completion require recorded native validation. A fixture pass cannot satisfy these cases.
