# FFVII Rebirth Biome Randomizer

An experimental, reproducibly seeded enemy encounter mod for FINAL FANTASY VII REBIRTH PC, developed for [FFVII-Modding issue #44](https://github.com/AW1KSwinton/FFVII-Modding/issues/44).

The first pool covers five ordinary level-15 Grasslands encounters. Each contains two Orcs and either a Mandragora or a Kalm Fang. A seed chooses which of those two existing compositions each encounter uses. The seed remains fixed across respawns, loading saves and restarting the game; generating another seed changes the world mapping. This is build-time randomisation.

**Status: prototype; native validation pending.** Offline checks prove deterministic selection and preservation of every unselected table property. They do not prove valid placement, encounter completion or difficulty balance in the real game. See [the status ledger](biome-randomizer-mod.md).

Story, media, swamp, rare, boss, hunt and quest encounters are outside the target allowlist. The prototype changes one property in one field table and adds no rows. Other regions remain unchanged. It preserves enemy levels, enemy counts, AI, encounter IDs, triggers, rewards and respawn timings. It does not write saves.

- [Player and build guide](docs/GUIDE.md)
- [Design and safeguards](docs/HOW-IT-WORKS.md)
- [Research, decisions and dead ends](docs/HOW-WE-BUILT-IT.md)
- [Validation plan](docs/TESTING.md)

This mod was developed by an AI coding agent using Codex, with the owner setting the objective. The DataBuilder reader/writer comes from the owner's MIT-licensed Training Dummy project. Source code is MIT licensed. Original game assets and generated packages are excluded from this source repository.

FINAL FANTASY VII REBIRTH and its assets belong to their respective owners. This is an unofficial fan project.
