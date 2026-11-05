# FFVII Rebirth Biome Randomizer

An experimental, reproducibly seeded enemy encounter mod for FINAL FANTASY VII REBIRTH PC, developed for [FFVII-Modding issue #44](https://github.com/AW1KSwinton/FFVII-Modding/issues/44).

The first pool covers four ordinary level-15 Grasslands encounters. Each contains two Orcs and either a Mu or a Kalm Fang. **The agreed 1.0.0 behavior is runtime selection each time a cleared existing camp respawns.** The runtime implements that behavior as an unreleased prototype; the earlier fixed-package experiment remains as research. 1.1.0 targets random camp placements. See [release scope](docs/ROADMAP.md).

**Status: prototype; callback repair under native validation.** Earlier builds passed automatic native transitions at05 and30, both directions at05, restart persistence and living-group streaming without reroll. Camp23's Mu/two Orc fight also completed, but a UE4SS callback-state failure stopped its selector before the final deaths and its counter did not advance. This is a retained runtime failure, not a passed respawn test. A new persistent game-thread dispatcher replaces the asynchronous Lua loop; its native acceptance and final regression/conflict QA remain pending. Equal difficulty is not established. See [validation](docs/TESTING.md), [runtime design](runtime/README.md) and [packaging investigation](docs/PACKAGING-INVESTIGATION.md).

Story, media, swamp, rare, boss, hunt and quest encounters are outside the target allowlist. The prototype changes one property in one field table and adds no rows. Other regions remain unchanged. It preserves enemy levels, enemy counts, AI, encounter IDs, triggers, reward configuration and respawn timings. It does not write saves.

- [Player and build guide](docs/GUIDE.md)
- [Enemy categories and cross-category investigation](docs/COMPATIBILITY.md)
- [Experimental Mandragora arena correction](experimental/arena-correction/README.md)
- [Design and safeguards](docs/HOW-IT-WORKS.md)
- [Research, decisions and dead ends](docs/HOW-WE-BUILT-IT.md)
- [Validation plan](docs/TESTING.md)
- [Version scope](docs/ROADMAP.md)
- [Final regression and conflict review](docs/RELEASE-QA.md)

This mod was developed by an AI coding agent using Codex, with the owner setting the objective. The DataBuilder reader/writer comes from the owner's MIT-licensed Training Dummy project. Source code is MIT licensed. Original game assets and generated packages are excluded from this source repository.

FINAL FANTASY VII REBIRTH and its assets belong to their respective owners. This is an unofficial fan project.
