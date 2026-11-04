# Release scope

Owner decisions,2026-11-04.

## 1.0.0: random compositions at existing camps

Keep the game's existing ordinary camp locations and native encounter/respawn management. Choose a fresh biome/progression/arena-compatible composition each time a cleared camp legitimately respawns. Keep a living group's composition stable. Preserve bosses, hunts, scripted and quest-critical encounters. Provide reproducible selection for diagnostics without requiring a new package for each respawn.

The current build-time seeded package is a working baseline, not the finished runtime behavior. Its first pool has Mu/Kalm Fang plus two Orcs at four reviewed level15 Grasslands camps. Runtime lifecycle selection and broader validated pools remain development work. The experimental Mandragora correction proves one scoped category boundary can be crossed, not universal compatibility.

Acceptance includes native clear→respawn transitions with changed compositions, no reroll caused merely by a live group unloading, reproducible diagnostic sequences, protected encounters unchanged and ordinary encounter completion. Define and document mod-state persistence separately from game save data.

## 1.1.0: random camp placements

Target a larger bank of validated camp locations, roughly2.5times the original location count, with about half active at once and compositions selected on spawn. This implies approximately1.25times the original active-camp count. These are design targets, not implemented claims.

Validate arena/nav/streaming, spacing, activation/deactivation and progression exclusions for every new location. Never deactivate an engaged camp or strand encounter completion. New camp placement is outside1.0.0.

The observed69 Grasslands territory actors include special encounters and are not a count of ordinary camps throughout the game. A world-wide eligible-camp census remains to be done.
