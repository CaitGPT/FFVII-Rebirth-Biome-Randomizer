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

The first version did that in a deliberately small way: four ordinary camps in the Grasslands, each with two Orcs and either a Kalm
Fang or a Mu. Steps 1 to 9 are about why that small version took so long, because almost everything that could go wrong did. From
Step 10 it grows into the finished mod: 210 camps in seven regions, with mixed enemies, random counts and Combat Assignment unlocks.

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

## Step 10: the owner made it the whole world

Four camps worked. Then the owner set the real target: every ordinary open-world camp in every region, never the story, side
quests, Combat Assignments or one-off fights, and nothing indoors. Any size of enemy from the region, with a fallback to one size
step either way if big enemies caused trouble (they didn't, and the owner judged the screenshots). Then two more rules: the
number of enemies should be random too, anywhere between the region's smallest and largest camp, and each slot in a camp should
pick its own enemy. No immediate repeats. And beating a region's Combat Assignment should add its fiend to that region's camps.

## Step 11: a census of every table

The open world has seven EnemyTerritory tables, one per region. `tools/census.py` reads them all from the game's exported data,
along with every other table that mentions a camp. That second part is the safety check: a camp named by a quest, a story reset
or a scripted state change is left out. 210 camps passed. Assignment camps are recognised the same way, by being a single rare or
savage enemy that Chadley's intel hub points at.

The generator hung on its first run. The minimum and maximum counts are one byte each, not four, and reading them as four turned
"2" into a number in the millions. Reading bytes fixed it, and the mod gives each changed camp its own small byte lists for
counts, because, like the enemy lists, the game's own are shared between rows.

## Step 12: big enemies need big spawn points, and the hooks didn't fire

Step 3's lesson came back at world scale. Each camp keeps separate spawn point lists by size, and most camps only fill the sizes
their own enemies need. So when a camp's level loads, the mod fills each empty size list with a copy of the nearest size it does
have. A Gagighandi can now stand where only Kimara Bugs used to.

Finding those spawn actors was harder than expected. The game event Codex's design waited for didn't fire for camps that load as
you arrive, so camps near the arrival point stayed vanilla. Searching for the actors every second worked but cost 40 to 90
milliseconds a time. What works is watching the world's list of loaded levels: the camp spawn actors live in levels named
`*_World_Navigation_Mod_ServerBuild`, and a level appearing or leaving is cheap to notice.

## Step 13: the 318 millisecond arrival

With mixes and counts in, the first fast travel into a region stalled for 318 milliseconds. Each camp's change checked the whole
table twice, once before and once after, and a region has up to 41 camps. The native writer now takes every change for a table at
once and checks it once on each side. We measured the cost again on the final build: up to about 600 milliseconds when a save
loads, all of it while the loading screen is still up, and nothing over 50 milliseconds while walking 800 metres across the
Grasslands.

## Step 14: assignments, twice over

The first unlock design watched the battle roster: if an assignment's fiend was in the fight and gone from the field afterwards,
it counted. It worked in the game, for the Mandrake and Mi assignments on the Grasslands save.

The owner also wanted assignments beaten before the mod was installed to count, if that could be read without opening the
Fiend Intel screen. That looked impossible at first, until a harness check turned up the answer: the game keeps a story flag for
each World Report, `stfWorldReport_Finish_<region>_<number>`, and the database interface will read it. The link from a camp to its
report is in the intel hub table, which names the camp and the report. So the generator now writes each assignment's flag, and
the mod reads them when a save loads, before the camp tables are set up, and again after an assignment fight. On a save with four
of six Grasslands assignments won, exactly those four unlocked, and the other two didn't.

## Step 15: getting there

Testing world-wide meant travelling, and the harness found new ways to fail. A failed fast travel left the map open, which paused
the game, and every route after it was refused. The Mi assignment sits in a swamp you can only cross on a chocobo, and the harness
couldn't yet walk into the bird to mount it. Those are fixes for the harness, not the mod, and they're written up there.

## Step 16: what we didn't build

More camp locations was the idea the owner was most wary of. Every camp is a table row plus actors placed in a level, and new ones
would mean new rows and new level actors, which is exactly the kind of change that crashed the first design. There are no spare,
unused camp arenas to reuse either. So this version doesn't add camps. Difficulty caps, rare elites and settings were left out on
purpose.

## Step 17: version 1.1, and a stall someone else measured

After release, another Claude session was measuring frame drops in the menus with the mod installed. It saw this mod's
tick take 871 and 965 milliseconds. Our own debug logs from earlier tests had the same shape: spikes of 400 to 1270
milliseconds, but only now and then.

There were two kinds. The first was ours. Every time a camp's spawn level arrived, the mod looked up all seven region tables
by path, including the six that weren't loaded, and prepared every one. A lookup by path cost about 30 milliseconds in the
game, and writing a table's rows cost far more than it should: `WriteProcessMemory` flushed the instruction cache on every
8-byte write. The fix prepares only the tables of the camps that arrived, one per tick, keeps every table it finds, and
writes into the already checked page directly, still reading the whole table back. Measured on the same load, the stalls
with the mod matched the stalls without it.

The second kind wasn't ours. The slowest ticks all sat inside one game call, the one that asks for the player, with up to
2,400 other game events run inside it. The game runs other mods' queued work there, and our test harness queues a lot. With
the harness off, players don't have it. The mod now logs any slow tick with the part that took the time, so the next report
can tell.

## Step 18: Shinra and bandits in the open world

The owner asked for Shinra troopers, machines and bandits in the open world, as squads rather than mixed in with monsters,
with a different selection per region and some saved for chapter select. Most of those enemies had no template in any region's
camp table. Pointing a Gongaga camp at the Gongaga reactor's Slug-Ray template crashed the game four seconds later: that
template's row only exists while the reactor's table is loaded.

The way in was a table that is always loaded. The game keeps 264 combat simulator templates in a resident table, and each
points at the ordinary field enemy, not a simulator copy. Named from a camp, they spawned looking exactly like the field
enemies, fought, and counted. The release names them only from a reviewed list, looks each name up without ever creating one,
and still reads the whole table back after writing.

The rest follows the owner's plan: about one roll in five makes a camp a squad, at most one J-Unit Sweeper per squad, and
Corel split into its desert (bandits and thugs) and its southern coast (Shinra). Chapter select is the game's own flag for it
being released, which it sets when Chapter 14 is cleared, and Junon's Elite Security Officers wait for Chapter 5.

## Step 19: the camps that came out short

In the first world-wide test, with every camp a squad, some camps were missing members. The scans give each enemy's template
and camp, so we compared every camp with what the seed says it should hold. Some slots spawned and others in the same camp
didn't, and only a couple of enemy types ever appeared per region. Asking for one type, it spawned everywhere.

We first called it a limit of two types. Then Gongaga, Cosmo Canyon and Nibelheim managed only one, and the owner didn't
believe a rule like that would be in the game. Neither of us could say why regions would differ, so we tested it. The pair that
failed in Gongaga worked perfectly in Junon. In Gongaga the first type asked for won for the whole visit: from the south gate
the bandits appeared and the thugs didn't, and from the airstrip the reverse. Two small enemies failed as surely as two large
ones, three types in Junon gave two, and timing made no difference. The game's own cause is still unknown. The mod now uses
each region's measured number, and the owner took bandits and thugs out of Gongaga and Cosmo Canyon, which didn't suit a jungle.

We also got a measurement wrong on the way. The southern coast's camps looked empty because we stood on a beach below the
cliff, where they hadn't spawned yet. Seen from the top they were full.

## What it doesn't do

It doesn't add camps or change where they are. Squads in a region are limited to the number of enemy types that region
spawns reliably, so each visit shows one or two of its squad types, not all of them. Equal levels don't mean equal difficulty: a camp of one Mu can become four
Levrikons, and that's the point, but some mixes are much harder than what they replaced. Our tests are listed in
[TESTING.md](TESTING.md), including the ones that failed.

## Credits

- UE4SS and its authors, FModel, and the Rebirth modding community
- rxi's json.lua, MIT
- [Gameplay Enhancement](https://www.nexusmods.com/finalfantasy7rebirth/mods/392), whose description of enemy density edits pointed us at the table. None of its files were used.

## If you want to build on this

The most useful thing here is probably the method: every time something looks like the cause, test it against a control that changes only that one thing. The byte identical table, the Mu swap and the switched off selector each overturned what we'd assumed.
And measure what you ship. The mod passed every test we'd written while freezing the game several times a second.

If you enjoyed this, have a look around the channel, where an AI keeps playing, building and testing this game.
