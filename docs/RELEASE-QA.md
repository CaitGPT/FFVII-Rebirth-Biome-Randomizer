# Final regression and conflict review

Required release gate requested by the owner,2026-11-04. Run after the intended1.0.0 runtime implementation is complete. A passed baseline or synthetic fixture cannot pass a native case. Record build/config/seed/game/UE4SS hashes, actual outcomes, evidence and remaining limitations. Preserve failed runs and full recordings. Review the final implementation for consequences outside its demonstration camp.

| Area | Required check |
| --- | --- |
| Change scope | Independently compare all output rows/properties and every packaged path with originals. No unintended assets or protected rows change. Runtime writes require exact allowlisted identity and reviewed category/capacity. |
| Protected encounters | Native representative story/scripted, quest/hunt and boss encounters retain composition, triggers and completion. Do not advance a protected story merely for testing. Explicitly mark unreachable cases untested. |
| Other regions | Region transition away/back preserves normal gameplay; unconfigured regions receive no substitutions. Check unload/reload and fast travel. |
| Spawn lifecycle | First spawn, complete clear, legitimate respawn, live-group stream-out/in and repeated visits. Reroll only at the configured lifecycle boundary. No duplicate/overlapping groups, partial replacement or reroll during battle. |
| Combat outcomes | Each admitted composition has reachable enemies, working attacks/AI, targeting, retreat/re-entry, victory/rewards and a clearable camp. Inspect enemy remnants and trigger state. Defeat/retry must not corrupt the selection or duplicate rewards. |
| Save/load | Save/reload and restart preserve documented runtime state semantics. A load of an earlier save must not falsely count a clear or inherit an unrelated in-progress encounter. Never write protected saves during tests. |
| Balance and arena | Counts, levels, progression and HP-budget constraints hold. Ground/flying and physique-specific points are valid. No unreachable enemies, impossible barriers or trapped player. Do not equate a coefficient bound with equal difficulty. |
| Installed mods | Test the actual supported mod set. Detect another override of the same territory asset or runtime writer; document priority/incompatibility. A script must not claim ownership of another mod's write. |
| Removal and failure | Removing the package and optional runtime component restores native behavior without requiring a modded save. Missing/stale state, unsupported game version, bad pool and uncertain write fail safely with useful logs. |
| Performance | Bounded hooks/polls/logs and state storage; no retained UObject wrappers across unload, runaway allocations, repeated writes or unbounded work per frame. |
| Distribution | Release contains only intended source/config/docs and installable mod output. No original assets, secrets, raw evidence or accidental dependency binaries. Verify archive contents and exact hashes. |

The final report must separate passed native checks, offline checks, known failures and untested cases. Unresolved material regression risks block release acceptance. Publication still requires the owner's separate approval under the installed create-rebirth-mod skill.
