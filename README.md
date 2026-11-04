# FFVII Rebirth Biome Randomizer

An experimental, reproducibly seeded enemy encounter mod for FINAL FANTASY VII REBIRTH PC, developed for [FFVII-Modding issue #44](https://github.com/AW1KSwinton/FFVII-Modding/issues/44).

The first pool covers four ordinary level-15 Grasslands encounters. Each contains two Orcs and either a Mu or a Kalm Fang. The current baseline package uses a build-time seed and stays fixed across respawns. **The agreed1.0.0 target is runtime selection each time a cleared existing camp respawns.** That lifecycle behavior is in development; the baseline package does not implement it.1.1.0 targets random camp placements. See [release scope](docs/ROADMAP.md).

**Status: prototype; native completion verified at05 and29.** One Mu and two Orcs spawned and cleared at05 in a single-target control and at29 in the full seed3 build. The full build also showed the expected compositions at05 and23. Camp30, alternate-seed replay and the runtime lifecycle remain pending. Offline checks additionally prove deterministic selection and preservation of every unselected table property. Equal difficulty is not established. See [the validation plan](docs/TESTING.md) and [packaging investigation](docs/PACKAGING-INVESTIGATION.md).

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
