# FFVII Rebirth Biome Randomizer

A FINAL FANTASY VII REBIRTH PC mod that changes which enemies you meet out in the open world. When a field camp comes
back after you've fought it, it can come back as a different mix of that region's enemies, in a different number.

An AI coding agent built this mod: Codex started it, Claude (Anthropic's model, in Claude Code) finished it, and the
owner set the goals and judged the results. The [testing notes](docs/TESTING.md) say what was tried in the real game
and what wasn't.

[Download on Nexus Mods](https://www.nexusmods.com/finalfantasy7rebirth/mods/2489) · [GitHub release v1.0.0](https://github.com/AW1KSwinton/FFVII-Rebirth-Biome-Randomizer/releases/tag/v1.0.0) · [Watch the demonstration and build story](https://www.youtube.com/watch?v=_2Okhf8-NwM)

## What it does

- **210 open-world camps** in the Grasslands, Junon, Corel, Gongaga, Cosmo Canyon, Nibelheim and the Midgar outskirts.
- **A random mix of that region's enemies.** Each slot in a camp picks its own enemy from the enemies that region's
  camps already use, so a Grasslands camp might come back as two Elfadunks and two Levrikons.
- **A random number of enemies**, anywhere between the region's smallest and largest existing camp.
- **No immediate repeats.** A camp's new roll always differs from the one before it.
- **Combat Assignments add to the pool.** Beat a region's Fiend Intel fiend (before or after installing) and it can
  start turning up in that region's ordinary camps.
- **Any fight counts.** A fight against a camp moves it on to its next roll however it ends (a win, or running
  away), unless it ends in a Game Over.
- **Nothing scripted is touched:** story fights, side quests, the Combat Assignments themselves, bosses, hunts,
  towns and interiors stay as they are.

Enemy levels, rewards, respawn timers and camp locations are the game's own. The mod never writes to your save files.
Its seed and each camp's counter live in `%LOCALAPPDATA%\FFVIIRebirthBiomeRandomizer\state-v1.json`.

## Install

You need [RE-UE4SS for FF7 Rebirth](https://www.nexusmods.com/finalfantasy7rebirth/mods/267) 1.0.2. Extract the
release zip into the game's folder, the one with `ff7rebirth.exe`. The mod checks the loader it runs under and stays
switched off on a build it wasn't tested with. The [guide](docs/GUIDE.md) covers installing, removing, and sharing or resetting
a seed.

## Known issues

- Unlocked assignment fiends belong to the install, not the save: loading an older save doesn't lock them again.
- Loading a save takes up to half a second longer while the mod sets up the camp tables, behind the loading screen.
- Agent play tests covered the Grasslands and Gongaga; the owner also playtested Corel. The owner's Corel report
  does not specify individual cases. Respawns in Cosmo Canyon, Junon and Nibelheim have not been watched in play by us.
  See [testing](docs/TESTING.md).
- Mixes can be harder than the camp they replace, and big enemies can turn up in tight spots. That's the point, but
  expect the odd strange-looking camp.

More in the [guide](docs/GUIDE.md#known-issues).

## Documentation

- [Player guide](docs/GUIDE.md): install, remove, seeds, what to expect
- [How it works](docs/HOW-IT-WORKS.md): the camp tables, the spawn points, the counters
- [How we built it](docs/HOW-WE-BUILT-IT.md): the whole story, dead ends included
- [Testing](docs/TESTING.md): what was tried in the game and what came out
- [Building from source](runtime/BUILDING.md)
- [Changelog](CHANGELOG.md)

## Licence

The source code is MIT licensed ([LICENSE](LICENSE)). The repository contains no game files. The camp lists in
`runtime/Scripts/world_pools.lua` and the offsets in `runtime/Native/src/reviewed_layout.hpp` are generated from your
own copy of the game's data by `tools/world_layout.py`.

FINAL FANTASY VII REBIRTH and its assets belong to Square Enix. This is an unofficial fan project, not affiliated with
or endorsed by Square Enix.
