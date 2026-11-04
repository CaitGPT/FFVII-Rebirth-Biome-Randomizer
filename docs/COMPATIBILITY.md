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

The original category1 Kalm Fang to category0 Mandragora change repeatedly crashed. Full asset preloading, rooted retention, ForceCreateActor and their combination did not solve it. The mismatch is now the leading hypothesis, not a proven root cause.

The reconstructed SDK exposes separate `TerritoryGroundSpawnPoints_S/M/L/2L/3L/4L` transform arrays on EndFieldEnemyTerritoryServerBuildActor, and separate flying arrays. The repeated crash reads a transform through a null-base array. A missing size-specific spawn list is consistent with this, but the SDK has declarations rather than the shipped selection implementation. Direct arena inspection and a controlled correction are required.

## Crossing the boundary

Possible implementations are to supply valid points for the replacement's native category in the particular arena, or give only the replacement instance an appropriate scoped category definition. Changing every Mandragora globally could invalidate its original arenas. Size labels also do not prove collision, navigation, animation, AI, streaming, rewards or completion safety.

At18:09 UTC a read-only runtime snapshot found69 server-build actors, matched by exact territory name. Camp05 has12 medium ground transforms and zero small transforms;23 has20 medium,29 has22 medium,30 has13 medium, all with zero small. Native Mandragora/Orc camps01 and02 have both small and medium lists (15 and18 transforms respectively). Their first three sampled small/medium translations match. Levrikon-only camp13 (category2) has9 large points; observed Elphadunk-only camps12/22/25/28 and swamp01 (category3) have only2L ground lists. These observations support0=S,1=M,2=L,3=2L for these ground encounters. This is direct evidence of the missing small list, and strengthens the category-specific spawn lookup hypothesis. It does not by itself prove that adding the list fixes the crash.

No cross-category fix is accepted yet. Preserve failed native tests and original save files. The next bounded experiment supplies only the missing small-category points for camp05, retaining native encounter management and Mandragora's original definition.
