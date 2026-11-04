# Enemy replacement categories

This is a source-data category map, not a proven universal interchangeability matrix. The original resident CharaSpec table contains 461 `EN...` character-spec variants. [The lookup CSV](enemy-categories.csv) lists their exact PhysiqueSize, MoveType and scale fields. Alternate states and boss parts are separate specs, not separate ordinary enemies.

The reviewed Grasslands template mappings are:

| PhysiqueSize | MoveType | Regional templates |
| --- | --- | --- |
| 0 | 0 | Mandragora, rare Mandragora, regional Vice/bandit variants |
| 1 | 0 | Kalm Fang, Mu, Orc, ordinary WereRat_Poison (Toxirat), rare Kalm Fang, rare WereRat_Poison (Venorat) |
| 2 | 0 | Levrikon, rare Levrikon, rare Mu |
| 3 | 0 | Elphadunk, rare Elphadunk |
| 3 | 2 | Quetzalcoatl |

Rare, quest, hunt and boss entries are listed to explain categories, not admitted to the ordinary pool. The regional table also has story-specific bandit templates. Their presence in a category never authorizes a replacement.

The full lookup has numeric size categories0..5 and movement0..3. Ground movement0 is established for the listed ordinary enemies. Quetzalcoatl uses2 and alternates flight/ground. Do not invent labels for every movement value, or claim an exact numeric size-to-S/M/L mapping before verifying it.

## Native observations

At Grassland_mob_05, replacing one category1 Kalm Fang with one category1 Mu retained two category1 Orcs, spawned all three with exact territory-tagged actor identities, and completed. Native logs reported Mu defeated and EXP/AP/gil rewards; the party returned to the field. This validates that specific replacement and arena. It does not validate every pair sharing size1.

The original category1 Kalm Fang to category0 Mandragora change repeatedly crashed. Full asset preloading, rooted retention, ForceCreateActor and their combination did not solve it. Supplying the missing small spawn list subsequently allowed the same three-enemy package to spawn and fight. A separate one-enemy diagnostic also completed. This supports the missing list as the operational cause in this arena; it does not establish every internal engine step.

The reconstructed SDK exposes separate `TerritoryGroundSpawnPoints_S/M/L/2L/3L/4L` transform arrays on EndFieldEnemyTerritoryServerBuildActor, and separate flying arrays. The repeated crash reads a transform through a null-base array. A missing size-specific spawn list is consistent with this, but the SDK has declarations rather than the shipped selection implementation. Direct arena inspection and a controlled correction are required.

## Crossing the boundary

Possible implementations are to supply valid points for the replacement's native category in the particular arena, or give only the replacement instance an appropriate scoped category definition. Changing every Mandragora globally could invalidate its original arenas. Size labels also do not prove collision, navigation, animation, AI, streaming, rewards or completion safety.

At18:09 UTC a read-only runtime snapshot found69 server-build actors, matched by exact territory name. Camp05 has12 medium ground transforms and zero small transforms;23 has20 medium,29 has22 medium,30 has13 medium, all with zero small. Native Mandragora/Orc camps01 and02 have both small and medium lists (15 and18 transforms respectively). Their first three sampled small/medium translations match. Levrikon-only camp13 (category2) has9 large points; observed Elphadunk-only camps12/22/25/28 and swamp01 (category3) have only2L ground lists. These observations support0=S,1=M,2=L,3=2L for these ground encounters. This is direct evidence of the missing small list, and strengthens the category-specific spawn lookup hypothesis. It does not by itself prove that adding the list fixes the crash.

The scoped correction supplies only the missing small-category points for camp05, retaining native encounter management and Mandragora's original definition. It is separate from the default size-matched seeded pool. Preserve failed native tests and original save files.

The first two control lookups did not resolve this streamed actor and left the small list empty. The third used fresh class enumeration with an exact full-name check, matching the successful read-only observation. With the unchanged Mu package, the scoped write verified all twelve copied FTransforms and an independent snapshot confirmed S12/M12. Comparing array counts for all69 server-build actors found exactly one change: camp05's S list0->12. The game and Mu1+Orc2 composition remained valid.

Reinstalling the exact previously crashing Mandragora1+Orc2 table package with that companion produced all three expected territory-tagged actors and native combat. The party lost that attempt on Hard, so mixed-group completion is unverified.

At the owner's request, a separate diagnostic reduced camp05 to one level15 Mandragora. It changed only five frozen-array logical lengths, preserving the original asset size, all other rows and the same arena correction. The fight completed on Hard: native messages reported Mandragora defeated,188gil,1524EXP/3AP and a pearl ginger root; fresh telemetry and an inspected capture confirmed return to the field. Cloud remained901HP and received no healing/revival command. Difficulty and chapter were unchanged; the owner's checkpoint was preserved.

This verifies cross-category spawning, active combat and single-enemy completion at05. It does not prove every same-category pair, other arenas, mixed-group completion or equal balance. [Experimental source and reproduction instructions](../experimental/arena-correction/README.md) are retained separately from the default package.
