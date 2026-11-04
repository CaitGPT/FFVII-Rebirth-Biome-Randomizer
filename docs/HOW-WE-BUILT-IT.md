# How we built it

## Why start with the Grasslands

The objective was to vary exploration encounters while keeping enemies in an appropriate environment. A worldwide shuffle would have made it harder to distinguish a bad arena from a bad enemy choice. We began with a small group of ordinary Grasslands encounters and two compositions the game already uses there.

## Following the spawn data

The regional territory table names the enemy templates, levels and counts. A second table connects those templates to battle character specifications. Other fields describe waves, triggers and special encounter behavior. Those connections gave us a way to choose a pool from actual game references rather than guessing from enemy names.

An ordinary-looking row turned out to have story and reset references. We left it and its media variant untouched. The prototype instead uses a short list of other encounters, and keeps everything else unchanged.

## Keeping the first change small

Earlier local mod research reported that adding a new territory row could break simulator fights. We did not reproduce that experiment here. The prototype edits existing rows and adds nothing. The first candidate exchanged Mandragora and Kalm Fang; the category investigation below explains why the default pool now exchanges Mu and Kalm Fang. It leaves two Orcs in place and keeps the same levels and number of enemies.

This is a narrow starting point. It lets us test a real change without claiming that every enemy in the region belongs in every arena.

## A world we can reproduce

The seed determines each encounter independently. Loading a save, revisiting an encounter or taking another route does not reroll it. Another seed can produce a different mapping. That makes it possible to return to the same location and investigate exactly what changed.

The audit records both the original composition and the selected one. An unchanged choice is recorded too. This gives the test an expected result to compare with the game.

## What offline tests establish

Synthetic tests exercise reproducibility, meaningful variation across seeds, pool membership, protected rows and refusal of changed progression or authored flags. An independent comparison of the built table checks that no unrelated property changed.

These checks establish properties of the generator and its output. They do not show that the game mounted the package, that an enemy fits the arena or that a battle can finish. Those conclusions need their own real-game evidence.

## Tools and credits

| Tool | Purpose |
| --- | --- |
| FModel raw exports | Read the owner's original game data |
| Training Dummy DataBuilder, MIT | Read, modify and verify the DataObject format |
| Python standard library | Deterministic selection, auditing and independent comparisons |
| UnrealReZen | Pack the modified table |
| Project gameplay harness and OBS bridge | Controlled native tests and recorded evidence |

The existing Gameplay Enhancement mod's Enemy Density description demonstrates related spawn-count editing. Its permissions prohibit reuse without permission. No files or implementation from that mod were used. The research link is in the status ledger.

## The size-specific spawn-list investigation

The first design treated Mandragora and Kalm Fang as small ground enemies. That classification was too loose. Original CharaSpec data gives Mandragora PhysiqueSize0, Kalm Fang/Mu/Orc1, Levrikon2 and Elphadunk3. Ground MoveType0 alone does not make them interchangeable. The generator now checks the numeric categories and the complete regional mob to BattleCharaSpec to CharaSpec chain.

Asset preloading, rooted retention, ForceCreateActor and their combination did not fix the Mandragora crash. A same-size Mu replacement did: exact territory-tagged Mu1+Orc2 actors spawned at05, fought and cleared, with native defeat/reward messages and return to field. The owner's new slot22 checkpoint beside the camp made repeat loads much faster. It is separately backed up and never reassigned as a registered model run.

A request-only read-only diagnostic then inspected69 actual server-build actors. Camp05 had12 medium ground spawn transforms and zero small ones. The native Mandragora/Orc camps01 and02 had both small and medium lists. Their sampled positions matched. Other researched size1-only targets also had only medium lists; native Levrikon-only camp13 had large points. This is much stronger evidence for a size-specific spawn capacity boundary, though it still needs a controlled correction before claiming the crash's cause.

The scoped experiment supplied only camp05's missing small list from that arena's existing medium transforms. A Mu control verified all twelve transforms; an independent comparison over69 actors found no other array-count change. The previously crashing Mandragora1+Orc2 package then spawned and fought, although the party lost on Hard.

The owner proposed isolating one enemy rather than changing difficulty. A separate diagnostic shortened five camp05 frozen-array logical lengths to1 while retaining their capacity, backing storage and the original package size. Complete DataBuilder exports showed only the intended five properties changed, and retoc decoded the packed payload exactly. One Mandragora spawned and the fight completed on Hard, with explicit defeat/reward messages and return to the field. Cloud stayed at901HP. No chapter restart, difficulty change or healing command was used. The five synthetic Lua guard tests passed under Lua5.4; they are separate from this native evidence.

The [experimental source](../experimental/arena-correction/README.md) preserves that narrow result and the failed controls. The default randomizer still uses size-matched compositions and requires no Lua companion. One-enemy completion does not substitute for the full seeded-pool acceptance or prove every mixed group is safe.
