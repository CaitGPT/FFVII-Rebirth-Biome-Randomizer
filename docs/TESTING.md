# Validation plan

## Offline

Run `python -m unittest discover -s tests -v`. The committed tests use explicitly synthetic data. Build a plan, then the single-target package, from the owner's hash-verified original assets. Independently compare every output property with the original. For representative seeds, check that both permitted small-enemy choices occur and the rest of each composition is identical.

## Native sequence

1. Back up saves and installed artifacts and verify the copies. Record exact package and probe hashes. Confirm compatible topology and a ready silent recorded session through the project bootstrap.
2. Test the smallest changed package first: algorithm v2 seed `3`, initially only `Grassland_mob_05`, whose selected composition is one Mu and two Orcs. Identify that actual territory and its physical arena; do not infer success from an unrelated Mandragora encounter.
3. Traverse to it through the gameplay harness. Observe the spawned actor/spec IDs and counts. Engage it and require a verified victory with return to the field, preserving any failures and the full recording.
4. Check an excluded encounter, including the story/reset-linked territory when safely reachable, and compare its original composition and completion behavior. Do not start a new story branch just to force this case.
5. Close the game normally and close the recording normally. Generate a different seed that selects the alternate composition at the same target. Build and install outside the recording, restart, and repeat the same route and completion check.
6. Repeat the original seed to test reproducibility after reload. Check the full four-target build across the controlled biome, recording exact territory identity and matching it to its audit.
7. Test respawn and save/load stability without overwriting protected slots. Test compatibility with the installed mod set. A changed package requires another installed-hash receipt.

Register production-test context before each recorded demonstration and end it immediately after the observed action. The event hook may verify the traversal or combat outcome; it does not independently prove that a mod's composition matches the seed. Preserve that comparison as separate native evidence. The gameplay client emits evidence only; the independent production worker owns editing and release media.

## Acceptance boundary

Do not mark issue #44 complete until the requested native seeded traversal, composition, placement, completion and protected-encounter checks are observed. Do not label a package tested or ready for release because the generator passed tests. Preserve uncertain and failed results.

## Observed 2026-11-04

The private matched-size single-target package passed Ranch travel, exact simultaneous territory-tagged Mu1+Orc2 inventory, battle initiation, ordinary enemy behavior and encounter completion at05. Native reward messages reported Mu defeated and EXP/AP/gil; fresh field telemetry and a window capture confirmed the return to the arena. No healing/revive command was sent to Cloud. Slot22 is the owner's backed-up near-camp checkpoint; it is not a model run assignment. A verified reload returned to that exact position.

The full algorithm-v2 seed3 package then loaded successfully without any experimental arena scripts. Complete actor inventory simultaneously showed exact Mu1+Orc2 groups at05,23 and29. A controlled189m route reached29; its native combat completed, with Orc A defeated,2096EXP/3AP and235gil messages and a verified field return. Cloud ended199HP; no healing/revival was issued. Camp30 remains unverified: a later route timed out and a requested fast-travel spot was unavailable. Full recording19-31-03.mkv and failure evidence are retained. Alternate seed6 and original-seed replay remain pending.

The separate Mandragora arena correction passed one-enemy spawning, combat and completion on Hard. The original three-enemy group spawned and fought with the correction, but the party lost. Preserve that distinction. See [experimental evidence boundaries](../experimental/arena-correction/README.md).

The original Mandragora attempts, raw/Zlib packaging failures and the unrelated unmodified transit-battle loss remain retained. Do not conflate these outcomes.

The manual-command fight exposed an evidence-hook limitation: registering and beginning a production context worked, but ending it refused because manual fights supply no completed routeResult. The context is unknown, not verified. Keep the direct native evidence and full recording; never manufacture a route result to make the event succeed.

The owner subsequently specified runtime rerolling on each cleared-camp respawn for1.0.0 and a [final regression/conflict review](RELEASE-QA.md). Build-time baseline results cannot pass that runtime release gate.

## Automatic runtime acceptance in progress

Twenty synthetic Lua 5.4 cases pass for the lifecycle policy, seed/cycle persistence, prepared-clear crash recovery, streaming rebind, defeat and conflicting writes. The native decoder also has a compiled argument regression. These are offline results.

Automatic native2 used DLL SHA256 `669e9084d0268ddd89cc9517e4813722c6f3577850ea802d76d192771b41661d`, adapter SHA256 `566e8a45e3df58ffa043f5e85b4e30d7f867b21b8fc25bd0041fc5ab062cd2b5`, seed `613`, original game data, and the actual installed mod set. Our earlier data package triplet was removed to a verified backup. Owner checkpoint22 remained hash-identical throughout.

The adapter acquired the original exact three-member groups at05,23 and29. One Orc died during an initial Hard-mode loss; all counters remained zero after verified Game Over. Retry reacquired fresh actors. A temporary, verified frontline swap replaced Cloud with Barret without saving. The subsequent original camp05 group cleared: each exact member produced zero-HP/native-Dead evidence, followed by one automatic cycle commit at22:10:05 UTC. The journal had05=1 and all other counters0.

Fast travel to Oliver's Farm, the unchanged180-second native timer, and a return route produced exact fresh Mu1+Orc2 at05 at22:13:42. The adapter independently logged `spawn_observed` cycle1/choice1. Groups23 and29 retained their original Kalm Fang/Orc actors. No manual setter request was used. This passes one automatic native clear-to-respawn transition, including partial-clear/defeat rejection. The full recording `2026-11-04 21-48-59.mkv`, failed attempt, raw logs, state journals, response JSON and captures remain outside Git.

Still required: nonzero-state restart/first-spawn timing; reverse/repeated transitions; living-group streaming without reroll; remaining arenas and broader pools; protected encounters, region transitions, mod conflicts, removal and the final [release QA gate](RELEASE-QA.md). No release acceptance or publication follows from this scoped pass.
