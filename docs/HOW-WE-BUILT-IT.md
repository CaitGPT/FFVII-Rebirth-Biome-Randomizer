# How we built Biome Randomizer

This is the story of the build, dead ends included. For the finished design in reference form, see [HOW-IT-WORKS.md](HOW-IT-WORKS.md). To
install and play, see [GUIDE.md](GUIDE.md).

## Why

Nobody is holding a controller here. This is Biome Randomizer, a mod for Final Fantasy VII Rebirth, and AI agents made it. Two of them, in fact. OpenAI's Codex
did most of the research and the first working version, then ran out of usage close to the end. Claude Opus 5.5, in Claude Code, picked up from Codex's notes and
finished it. Both of them researched the game, wrote the code, played the game to test it, and recorded the footage. A human set the goal, made the design calls
and caught problems the agents had missed, including the biggest bug in this story.

The goal was simple to say. When you go back to a camp of enemies in the open world, it shouldn't always be the same enemies. But they should still belong there,
and the game should still work: no broken fights, no story encounters changed, nothing strange in the wrong place.

The first version does that in a deliberately small way. Four ordinary camps in the Grasslands, each with two Orcs and either a Kalm Fang or a Mu. Most of this story
is about why that small version took so long, because almost everything that could go wrong did.

## Tools

| Tool | Used for |
| --- | --- |
| [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) 3.0.1, the Rebirth build | Running Lua and a small C++ module inside the game |
| [FModel](https://github.com/4sval/FModel) | Reading the game's own data tables |
| DataBuilder, from our Training Dummy mod | Reading and comparing those tables |
| UnrealReZen, then our own packer | Packing test archives, in the first design |
| Our test harness | Letting the agents drive the game: walking, riding, fighting, reading the screen |
| OBS | Recording every test |
| Python and Lua | Offline tests |

## Step 1: follow the spawn data

Enemy camps are described by a regional table called EnemyTerritory. The Grasslands one has 44 rows. Each row names enemy templates, levels and counts, and a second
table connects each template to a battle character. That gave us a way to choose enemies from what the game already does, rather than guessing from their names.

One ordinary-looking camp turned out to be tied to story and reset tables, so we left it alone. We ended up with four camps that are referenced nowhere else, each with
one Kalm Fang and two Orcs.

## Step 2: the first idea crashed, and the reason wasn't what it looked like

The first design was the obvious one: edit the table, pack it into a mod file, and let a seed decide which enemy each camp gets when you build it. Codex swapped one
Kalm Fang for a Mandragora and fast travelled to the Grasslands.

The game crashed. It crashed again on an unchanged retry. It would be natural to blame the Mandragora, so Codex tested that properly. With no mod at all, the trip worked.
With a table that was byte for byte identical to the original, just packed as a mod, it crashed anyway. So the enemy wasn't the first problem. The packaging was.

That sent us through a long list of controls. An inherited step was overwriting part of a compressed header. Installed mods were being pulled in as inputs. The package metadata
was missing. The table of contents was a newer version than other Rebirth tools write, with a different kind of hash. Each of those was real, and fixing each one
moved the crash without ending it. What finally worked was native Oodle compression, the older table of contents format, and a properly shaped empty header, which leaves the game's own
record to describe the asset. A package that changed nothing finally loaded, and the party reached Bill's Ranch.

## Step 3: Mandragoras need somewhere to stand

With packaging fixed, the Mandragora still crashed the game. Loading its assets ahead of time didn't help, and neither did keeping them in memory or forcing the actor to be created.

A Mu worked straight away. That was the clue. The game's data gives each enemy a physique size. Kalm Fangs, Mus and Orcs are all size one. A Mandragora is size zero. So Codex read the
real spawn lists from the running game, across 69 enemy territories, and found they're kept separately by size. Camp 05 has twelve medium spawn points and no small ones. The camps where Mandragoras
normally appear have both. Asking that camp for a small spawn point was asking for something that wasn't there.

Copying the medium points into the small list let the same three enemy group spawn and fight. The party lost that fight on Hard, so the owner suggested testing just one enemy instead of changing the difficulty.
One Mandragora spawned, fought and was defeated, with the normal rewards. It's a real result, and the code is kept in the repository as an experiment. But it doesn't prove every mixed group is safe, so the
release sticks to enemies of the same size.

## Step 4: the owner changed what the mod is

Then the design changed. The owner didn't want a seed baked in when you install. They wanted a camp to come back different each time you clear it. A packed table can't do that, because it's fixed when the game starts.

So the mod had to change the table while the game runs. Reading the live table showed a trap: several rows share one list of enemies, so editing the list would change camps we'd never reviewed. Instead, each row holds a small pointer to its list,
and the mod moves only that pointer, to another list the game already has. That's eight bytes. Before it writes anything, it checks the whole table against a fingerprint of the version we reviewed, and if anything differs, it does nothing. Afterwards it reads the whole table back and compares it.

That also means no game files are replaced at all, and the release has no data package. Early tests caught a callback running on a loading thread and an argument reader that consumed its values, and both are fixed.
The first native respawn worked: a camp cleared, the party travelled away, the game's normal three minute timer ran, and fresh Mu and two Orcs came back in the same place.

## Step 5: a win that didn't count

During final testing, the party won a fight at camp 23, and the counter didn't move. The fight was fine. The mod had stopped halfway through, because the scripting system had dropped the temporary Lua state it was running on. Codex wrote that up as a failure rather than quietly counting the win, then replaced the loop with
a small native dispatcher that runs on the game thread using the mod's one long lived Lua state. Then it ran out of usage, with fresh install and removal testing still to do.

## Step 6: the freezes

This is where the human mattered most. Claude had taken over and was running the last tests when the owner said the game was freezing, far more than usual, and that it might be from this work. That matters a lot here, because this game's footage goes on YouTube.

Every earlier test had asked whether the right enemies appeared. None had timed anything. So Claude added counters to the native module and measured. The mod's check, which ran several times a second, was taking between 60 and 88 milliseconds each time, on the game thread, just standing still.
A frame at 60 frames a second lasts about 17. By accident, a typo in a profiling script then disabled the mod for one run, and the owner said it felt better already. That was a clean before and after.

The surprise was where the time went. We'd assumed the enemy lookups, or the fingerprint check. Those cost almost nothing. Nearly all of it was finding the same objects by their path, over and over: the territory table, the player, and three game interfaces. So those objects are now found once, and the mod does almost nothing unless you're within 200 metres of one of the four camps.

The check went from about 70 milliseconds to about 0.2. Comparing the same spot, stalls longer than 50 milliseconds went from about one and a half per second with the old code, to 5 in a minute with the new code, and the same 5 with the selector switched off. The rest belong to the game and our test tools.

## Step 7: the owner's better rule

The old rule was strict: a camp only advanced once all three enemies had been individually proven dead. After the speed fix, that kept failing, with only one death of three recorded. Claude's first guess was that it now checked too slowly, and checking faster didn't help.

While that was being investigated, the owner suggested dropping it altogether. If you entered combat with a camp and didn't get a Game Over, either you beat them or you ran, and either way the counter should move. That's simpler and it's better for the player, so we adopted it, with two refinements. It's counted when the fight ends, so a wipe never needs undoing, and that camp has to actually be in the fight, so that battling something else nearby doesn't count.

Building that exposed why the old rule had been failing all along. Logging what the mod actually saw showed that during a battle, the game reports no player character at all, and the mod treated that as a loading screen and went to sleep. The interface Codex used to ask whether a battle was running also stays false through ordinary field fights. It had only ever worked by catching lucky moments. There was a useful surprise too: enemies report one hit point out of one until a battle takes them in, then their real health. That turned out to be an exact signal that a camp has joined a fight, even if you run away without landing a blow.

## Step 8: the crash when you quit

The owner also noticed a fatal error when closing the game, and said to make sure it wasn't this mod, because that would worry anyone who installed it. The crash reports showed that the same crash first appeared the day before this mod existed.

To be sure, Claude closed the game repeatedly in different setups. With our test tooling loaded, it crashed on nearly every close, with this mod or without it. With only UE4SS and this mod, as a player would have it, it closed cleanly. So the cause is in our test tooling, not this mod, and it's now a separate job for the harness.

## Step 9: making it safe to hand to someone else

A C++ mod is built against one exact version of UE4SS, and Nexus now lists several Rebirth builds. A mismatched one might crash the game rather than fail politely. So the module hashes the loader that's actually running before it touches anything, and if it's not the one we tested, it steps aside and says so in the log. We checked that the public 1.0.2 download contains exactly the file we tested against.

## What it doesn't do

It's four camps and two enemy choices. That's a small pool, and the bigger ideas, more enemies and new camp locations, are in the [roadmap](ROADMAP.md). Equal numbers and levels don't mean equal difficulty: Mu and Kalm Fang fight differently. Our tests are listed in [TESTING.md](TESTING.md), including the ones that failed.

## Credits

- UE4SS and its authors, FModel, and the Rebirth modding community
- rxi's json.lua, MIT
- [Gameplay Enhancement](https://www.nexusmods.com/finalfantasy7rebirth/mods/392), whose description of enemy density edits pointed us at the table. None of its files were used.

## If you want to build on this

The most useful thing here is probably the method: every time something looks like the cause, test it against a control that changes only that one thing. The byte identical table, the Mu swap and the switched off selector each overturned what we'd assumed.
And measure what you ship. The mod passed every test we'd written while freezing the game several times a second.

If you enjoyed this, have a look around the channel, where an AI keeps playing, building and testing this game.
