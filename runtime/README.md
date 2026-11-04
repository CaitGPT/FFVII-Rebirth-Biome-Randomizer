# Runtime composition work in progress

The1.0.0 target is a fresh compatible composition each time a cleared existing camp legitimately respawns. These files are a development experiment, not a player release. Automatic lifecycle selection and persistence are not implemented yet.

The native module and Lua component use the installed UE4SS3.0.1 beta c0a8d4c interface. A read-only native test located the live regional EnemyTerritory asset and its frozen content at the observed UObject+0x38 pointer. The first19536bytes have the same layout as the reviewed original export; runtime FName fixups differ as expected. Raw captures remain outside Git.

Identical composition vectors are shared between multiple rows. Editing their elements would change other camps. The guarded experiment instead changes only a selected row's existing frozen relative pointer to another existing two-template vector. Original vectors remain untouched. No allocation, new row, manual enemy creation, count/level change, respawn-timer change or save write is needed for this experiment.

`tools/runtime_layout.py` accepts only the reviewed original SHA256 and generates the name/offset/fingerprint manifest. It embeds no original asset payload. The native validator checks all126 name tokens and the entire normalized structural SHA256. Only four reviewed row references may point to either the native Kalm Fang+Orc vector or the native Mu+Orc vector. All counts, flags, levels, other rows and vector contents remain covered by the checks. A stale expected selection, unknown pointer, changed names, structure mismatch or nonwritable data refuses a write. An uncertain write permanently latches further writes off. Exact full-image readback must equal the prior image except for the requested eight-byte row reference.

The current Lua wrapper only performs explicitly requested diagnostics from a developer evidence directory. It schedules calls on the game thread and resolves the regional UObject afresh each time. It does not yet choose random groups, detect clears or manage respawns. The reference setter has compiled; native mutation/respawn acceptance is pending. Do not ship these diagnostic paths as the final user-facing runtime.

The runtime control starts from the original-composition table (build-time seed6). The prior seed3 package changes template-name fixups and should correctly fail the original-table manifest check. The final runtime should not require an overriding territory package when it uses the native original asset.
