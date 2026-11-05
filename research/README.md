# Research

Earlier designs, kept because the story in [HOW-WE-BUILT-IT](../docs/HOW-WE-BUILT-IT.md) refers to them. None of this is
part of the release, and these files aren't maintained: paths inside them may still point at their old places.

- `fixed-package/`: Codex's first design. A seed chose each camp's enemies at build time, and DataBuilder plus our own IoStore
  packer wrote the changed table into a mod archive. Includes the packaging investigation (why byte-identical packages crashed
  until the header, table of contents and compression matched what the game expects) and the enemy size study.
- `four-camp-prototype/`: the first runtime version, four Grasslands camps. `runtime_layout.py` generated its single-table
  layout. `arena-correction/` is the experiment that first showed a size-0 Mandragora can spawn in a camp with no small
  spawn points once those points are filled. `runtime-reference-diagnostic/` is the manual request wrapper used before
  automatic selection.
