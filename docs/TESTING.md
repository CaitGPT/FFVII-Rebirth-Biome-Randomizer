# Validation plan

## Offline

Run `python -m unittest discover -s tests -v`. The committed tests use explicitly synthetic data. Build a plan, then the single-target package, from the owner's hash-verified original assets. Independently compare every output property with the original. For representative seeds, check that both permitted small-enemy choices occur and the rest of each composition is identical.

## Native sequence

1. Back up saves and installed artifacts and verify the copies. Record exact package and probe hashes. Confirm compatible topology and a ready silent recorded session through the project bootstrap.
2. Test the smallest changed package first: seed `44`, only `Grassland_mob_05`, whose selected composition is one Mandragora and two Orcs. Identify that actual territory and its physical arena; do not infer success from an unrelated Mandragora encounter.
3. Traverse to it through the gameplay harness. Observe the spawned actor/spec IDs and counts. Engage it and require a verified victory with return to the field, preserving any failures and the full recording.
4. Check an excluded encounter, including the story/reset-linked territory when safely reachable, and compare its original composition and completion behavior. Do not start a new story branch just to force this case.
5. Close the game normally and close the recording normally. Generate a different seed that selects the alternate composition at the same target. Build and install outside the recording, restart, and repeat the same route and completion check.
6. Repeat the original seed to test reproducibility after reload. Check the full five-target build across the controlled biome, recording exact territory identity and matching it to its audit.
7. Test respawn and save/load stability without overwriting protected slots. Test compatibility with the installed mod set. A changed package requires another installed-hash receipt.

Register production-test context before each recorded demonstration and end it immediately after the observed action. The event hook may verify the traversal or combat outcome; it does not independently prove that a mod's composition matches the seed. Preserve that comparison as separate native evidence. The gameplay client emits evidence only; the independent production worker owns editing and release media.

## Acceptance boundary

Do not mark issue #44 complete until the requested native seeded traversal, composition, placement, completion and protected-encounter checks are observed. Do not label a package tested or ready for release because the generator passed tests. Preserve uncertain and failed results.
