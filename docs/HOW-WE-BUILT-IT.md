# How we built it

## Why start with the Grasslands

The objective was to vary exploration encounters while keeping enemies in an appropriate environment. A worldwide shuffle would have made it harder to distinguish a bad arena from a bad enemy choice. We began with a small group of ordinary Grasslands encounters and two compositions the game already uses there.

## Following the spawn data

The regional territory table names the enemy templates, levels and counts. A second table connects those templates to battle character specifications. Other fields describe waves, triggers and special encounter behavior. Those connections gave us a way to choose a pool from actual game references rather than guessing from enemy names.

An ordinary-looking row turned out to have story and reset references. We left it and its media variant untouched. The prototype instead uses a short list of other encounters, and keeps everything else unchanged.

## Keeping the first change small

Earlier local mod research reported that adding a new territory row could break simulator fights. We did not reproduce that experiment here. The prototype edits existing rows and adds nothing. It leaves two Orcs in place and chooses whether their companion is a Mandragora or a Kalm Fang, keeping the same levels and number of enemies.

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
