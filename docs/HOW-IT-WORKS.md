# How it works

## Current runtime prototype

The runtime changes compositions at four existing camps, using the game's normal population manager. It never manually creates enemies or changes a camp's location, count, level or respawn timer. Each reviewed camp contains two Orcs plus either one Kalm Fang or one Mu. The default pool needs only existing medium ground spawn points; the Mandragora small-point correction is a separate experiment.

An automatic seed is generated once through Windows BCrypt and stored outside game saves. An explicit seed supports reproducible diagnostics. For each camp, `sha256-respawn-v1` hashes the length-framed algorithm, seed, camp ID and complete-clear counter; the first eight hexadecimal digits modulo two choose the next composition. This differs from the historical package algorithm below. A valid new roll can repeat the same composition.

Only three exact, owned enemy identities at zero HP with native Dead state establish a complete clear. The party must be alive outside battle before committing it. Absence, partial kills, retreat, defeat and unloading are insufficient. A new party-actor epoch discards in-progress death evidence. Living groups keep their selection across streaming; fresh identities are rebound without advancing the counter. The state's seed and counters persist globally across saves; loading an earlier game save does not rewind them.

The native table uses shared composition vectors. Editing their elements would affect unrelated camps. Instead, each permitted eight-byte row reference is redirected to an existing reviewed vector. All126 name tokens and the entire normalized19536-byte image are checked first. Names, flags, other rows, vector contents and all unrelated properties stay protected. A stale selection or conflicting writer refuses changes; uncertain write readback permanently disables further writes.

The state store writes a prepared-clear intent before changing a reference, then commits only after exact native readback. Atomic Windows replacement, previous-file backup and state readback protect the four counters. A restart can finish a proved, prepared intent once; it cannot infer a clear from missing actors. Corrupt or incompatible state stops operation.

After native QA found a transient Lua-state failure, the paired DLL replaced the async Lua loop with a persistent main-state callback on the verified game thread. Its100ms pacing, re-entry guard and failure latch avoid queued coroutine growth. Early territory startup and owned-enemy destroyed events use that same state. The script retains string identities instead of UObject wrappers across unload. This architecture still needs its own recorded acceptance and final conflict QA; see [testing](TESTING.md).

## Historical fixed-package experiment

The remaining sections describe the earlier build-time generator and archive verification. That package is retained for research and is not installed alongside the runtime.

## Reviewed scope

The input territory table contains forty-four rows. Four are selected explicitly: `Grassland_mob_05`, `Grassland_mob_23`, `Grassland_mob_29` and `Grassland_mob_30`. Each originally has one Kalm Fang and two Orcs, levels `[15,15]`, counts `[1,2]`, and field AI `[1,1]`. The alternate species list comes from ordinary native donor18 (Mu2+Orc2); only the species list is used, so each target retains Mu1+Orc2.

The original regional mob table maps templates to BattleCharaSpec, and the resident BattleCharaSpec table maps those to CharaSpec. All three pool enemies have exact PhysiqueSize1 and MoveType0. The build binds all four original asset hashes and validates these mappings, HPDirect0 and exact HP coefficients. A target-population-weighted HP coefficient budget is630 for Kalm1+Orc2 and500 for Mu1+Orc2 (79.4%). This bounds one dimension of difficulty; it is not an equal-difficulty claim.

Mandragora has size0 and is excluded, including its native territory02. The prior Mandragora design crashed; the matched-size Mu replacement at05 spawned correctly and completed in game. See [the compatibility investigation](COMPATIBILITY.md). Matching categories establishes candidates, not universal swap acceptance.

The story/reset-linked territory01 and its Media variant, swamp, rare, hunt, quest and boss encounters are excluded. Neither enemy names nor a region prefix authorizes a target. Structural source checks and the exact allowlist constrain the change; map scripts and encounter completion still require native evidence.

## Legacy build selection

The algorithm hashes a canonical UTF-8 JSON array containing the algorithm ID, seed string, pool ID and target ID. The full SHA-256 integer modulo the number of sorted donor IDs chooses the donor. Sorting makes selection independent of dictionary and catalog list order. There is no global RNG state, current-time seed or dependency on route traversal order.

The builder changes only `MobTemplateList_Array` in selected rows whose choice differs from vanilla. It preserves all other properties and every unselected row. It adds no rows and leaves EnemyTerritoryMob and all other assets out of the package. Selecting a vanilla composition is valid and is reported as an unchanged choice.

## Verification

The builder first verifies original binary SHA-256 hashes, exports the tables using DataBuilder's long CSV format, and checks each reviewed target and donor's structural constraints, count budgets and complete character mapping. DataBuilder edits and rereads its own result. A separate Python comparison rereads the output CSV and requires the exact expected change in every row and property. Original input hashes are checked again before success.

The audit records the algorithm, seed, catalog and input hashes, per-target selections, modified asset hash and complete package hashes. Every IoStore block is decompressed and the packed asset is compared with the independently verified table. The final archive uses native Oodle compression, version-2 TOC fields, SHA-1 metadata and a valid Rebirth-shaped empty container header. The existing game's package-store metadata describes this existing asset. Generated packages remain labelled `packed_unvalidated` until a separate native test supplies evidence. The [packaging investigation](PACKAGING-INVESTIGATION.md) records the failed controls and why copying arbitrary UCAS prefix bytes was removed.

In this historical package, choices remain stable through save/load and respawn because the mapping is baked into the archive. The runtime above instead changes guarded in-memory row references and keeps separate mod state. Neither implementation writes game save files.

## Limits

Only one small Grasslands pool has been researched. Swamp ecology, flying enemies, large enemies, rare spawns, progression scaling, authored fights and other regions are excluded. Level and count matching bound the initial change but do not establish equal difficulty. Collision, AI, streaming and encounter completion require recorded native validation. A fixture pass cannot satisfy these cases.
