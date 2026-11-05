# Player guide

## What you need

- FINAL FANTASY VII REBIRTH on PC (Steam).
- [RE-UE4SS for FF7 Rebirth](https://www.nexusmods.com/finalfantasy7rebirth/mods/267) version 1.0.2, installed so
  that `End\Binaries\Win64\ue4ss\UE4SS.dll` exists. The mod includes a small native part (`dlls\main.dll`) that has to
  match the loader exactly, so it checks the loader's fingerprint when the game starts. On any other build it writes an
  `inactive` line to `UE4SS.log` and does nothing.

## Install

1. Close the game.
2. Extract the release zip into the game's folder, the one with `ff7rebirth.exe` in it. You should end up with:

   ```text
   End\Binaries\Win64\ue4ss\Mods\BiomeRandomizerRuntime\
     enabled.txt
     dlls\main.dll
     Scripts\main.lua, automatic.lua, lifecycle.lua, state_store.lua, biome_json.lua, world_pools.lua, config.lua
   ```

3. Start the game. `enabled.txt` turns the mod on, so you don't need to edit `mods.txt`.

To check it's running, open `ue4ss\UE4SS.log` and look for `[BiomeRandomizerRuntime]` lines with `selector_ready`
and `table_ready`.

## What to expect

The first time you load a save with the mod installed, each eligible camp gets its first roll, so camps that haven't
spawned yet will already be different. After that, a camp changes each time you fight it and it respawns. The game's own
timer and streaming decide when that happens: you normally need to leave the area for a few minutes.

- A camp counts as fought when its enemies join a battle that doesn't end in a Game Over. Winning, running away and
  leaving the fight all count. A Game Over leaves the counter alone, so a retry meets the same enemies.
- Each slot in a camp picks its enemy from the enemies the region's camps use. The camp's total number of enemies is
  picked between the smallest and largest camp in that region, so a camp of one can become a camp of four, and back.
- The new roll is never the same as the last one.
- When a region's Combat Assignment (Chadley's Fiend Intel) has been won, its fiend joins that region's pool. The mod
  reads the save's record when it loads, so assignments won before you installed it count too. Only assignments whose
  fiend is a single named enemy qualify: 31 across the seven regions.
- Levels stay with the camp: a swapped-in enemy gets the level the camp's own enemies had.

What isn't changed: story battles, side-quest fights, the Combat Assignments themselves, bosses, hunts, Chadley's
simulator, Queen's Blood, Colosseum fights, minigames, towns, dungeons and interiors.

## Seeds

`Scripts\config.lua` holds the settings:

```lua
return {
    enabled=true,
    seed='auto',
}
```

- `seed='auto'` makes a random seed the first time and keeps it.
- Any other text, for example `seed='cloud'`, gives a sequence that anyone with the same seed and the same fights will
  see too. Change it while the game is closed. A new seed starts every camp from scratch.
- `enabled=false` switches the mod off and leaves the state file alone.

The seed, each camp's counter and the unlocked assignment fiends are in
`%LOCALAPPDATA%\FFVIIRebirthBiomeRandomizer\state-v1.json`. They belong to the install, not to a save slot, so loading an
older save doesn't rewind them. Delete the folder to start again with a new random seed.

## Remove

Close the game and delete `Mods\BiomeRandomizerRuntime`. All the mod's changes are in memory, so the game is back to
normal the next time it starts. Your saves were never changed. You can also delete
`%LOCALAPPDATA%\FFVIIRebirthBiomeRandomizer`.

## Known issues

- **Unlocks belong to the install, not the save.** The mod reads each save's won assignments when it loads, including
  ones won before you installed the mod. Once a fiend is unlocked it stays unlocked, even if you load an older save that
  hadn't won that assignment yet. Delete the state folder to reset.
- **Loading takes a little longer.** The mod checks and sets up the camp tables when a save loads or you fast travel,
  up to about half a second. We matched it against recorded frames: it all happens while the loading screen is up. Walking
  around afterwards costs nothing noticeable.
- **Odd-looking camps.** Any size of enemy can turn up in any camp of its region, so a big enemy can end up in a tight
  spot. In our tests they spawned and fought normally.
- **Other mods that change the camp tables** (`EnemyTerritory` in any region) clash with this one. The mod checks each
  table's fingerprint and leaves a table it doesn't recognise alone, so it fails safe rather than mixing.
- **The game sometimes shows a fatal error when you quit.** We checked: with this mod alone the game exits cleanly.
  Other tools that hook the game can cause it, so if you see it, try without them first.

## Problems

Look in `ue4ss\UE4SS.log` for `[BiomeRandomizerRuntime]`:

- `inactive` with a reason: the loader or a camp table isn't the one the mod was tested with, and it's done nothing.
- `automatic_disabled`: something unexpected happened, so it stopped changing camps for this session. Camps it had
  already changed keep their enemies until you restart the game. Please report it with the log and your state file.
- `fight_observed`, `cycle_committed`: a fight was seen and a camp moved on.
- `assignment_unlocked`: an assignment fiend joined its region's pool.

Bug reports are welcome on the GitHub repository's Issues page.

## Build from source

See [runtime/BUILDING.md](../runtime/BUILDING.md).
