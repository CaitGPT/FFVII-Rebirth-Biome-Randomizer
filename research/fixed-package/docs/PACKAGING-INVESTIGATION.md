# Packaging investigation

## Controls and observations

The first build changed one byte in the original regional table: the relative pointer for one existing enemy-template array. Both attempts with that package crashed during Grasslands travel. The same save and destination succeeded after removing only BiomeRandomizer. An override containing the byte-identical original table also crashed. These controls establish that an enemy substitution is not necessary to trigger the failure.

The original table's serializer round-trip reproduced its bytes exactly. The source table and the archive therefore need separate verification.

## Compressed-block corruption

The inherited build recipe overwrote the first ten UCAS bytes with bytes from a vanilla container. In these archives the first bytes belong to a compressed container-header block. Independent decompression failed on that block after the overwrite, while the asset block still decompressed correctly. The build now preserves the packager's block data and decompresses every block during verification.

This recipe came from the owner's [Training Dummy build script](https://github.com/CaitGPT/FFVII-Rebirth-Training-Dummy/blob/main/tools/Build-TrainingDummy.ps1). Training Dummy's previously observed native behavior is separate evidence; this investigation does not claim that it cannot work. No installed Training Dummy files were changed.

## Duplicate chunks during rebuilds

The packager scans its game directory recursively. Including an installed BiomeRandomizer override produced duplicate chunk IDs in a subsequent build. The independent verifier refused that archive. Packaging now reads a view containing hard links to top-level vanilla archives, excluding installed mod subdirectories. It does not move or modify those original archives.

The build directory must be on the game's volume for these hard links. A permissions failure also prevents creating them; use normal native file access when running through a sandbox. They are source archive aliases, never outputs that a tool may edit.

## Missing Rebirth package-store metadata

The generic packager produced a container header declaring zero packages. Removing the corrupt byte overwrite alone produced a different failed startup; it did not establish game compatibility.

The original container's decoded header has an additional 32-bit field before its name batch. Its package-store records use 32-byte entries. The selected table's record identifies one export, one bundle, its original size flags and load order, and zero imported packages. These values are read from the original container, not guessed from the filename.

The corrected archive preserves only that selected package's entry and imports. It rebuilds the legacy header with the Rebirth layout, repacks the two raw chunks with retoc, preserves the container ID consistently, and independently verifies the table bytes and metadata again. Synthetic tests also exercise import relocation and refusal of invalid original metadata.

The raw packed control loaded the registered save but crashed during Grasslands travel. Padding the header to the original 64 KiB granularity did not resolve it; the aligned control produced the same native stack hash. A syntactically readable archive is not proof that the game accepts it.

## Legacy TOC and chunk hashes

The raw packer emits version-3 TOCs and newer chunk hashes. The game's original archives use version 2. A separately inspected Rebirth-specific writer also uses version 2 and SHA-1 chunk metadata. A private control preserved both decoded chunks exactly while selecting the legacy version, zeroing unused version-3 fields and recording SHA-1 metadata. It loaded slot 15 successfully but crashed during Grasslands travel with the same stack hash. These format changes alone did not resolve the failure.

The original container also carries an unexplained nonzero field and data after the legacy package-store structures. A further private diagnostic preserved the entire original header except its container ID. It declared the original package set and also crashed on the same travel. This was a diagnostic, not a release design.

## Native compressed-block control

A valid Rebirth-shaped empty header with the unchanged asset stored raw still crashed. A further control retained that header and directory but copied the asset's exact original Oodle-compressed block and original SHA-1/compression metadata. That control loaded the same save and successfully reached Bill's Ranch. A second no-mod baseline also reached the Ranch with the current harness. The source asset block is short (24,160 raw bytes) and begins at a 64 KiB boundary, so a short block or within-block offset alone does not explain the difference.

The new builder compresses edited table data through the owner's installed Oodle library, verifies exact decompression, writes the reviewed legacy layout and independently reads every resulting chunk again. An additional archive reader recovered the edited table's exact SHA-256. A freshly generated no-op override then loaded the registered working save and reached Bill's Ranch. This establishes native compatibility for the writer with unchanged data.

## Substitution initialization remains unresolved

The same writer with the one-encounter Kalm Fang to Mandragora substitution crashed before a verified save load. A separate two-asset diagnostic set the existing Mandragora mob template's ForceCreateActor flag while preserving all other mob properties. It loaded the working save successfully but crashed during Grasslands travel. The failed dumps and full recordings are retained; neither build is a release candidate.

The substitution crash differs from the raw-archive controls. Its top instruction reads a transform-sized array through a null base. This is evidence about the failing instruction, not proof of the original cause. The next diagnostic tests replacement-asset availability. Training Dummy's placed-actor requirement remains relevant, and no assumption that swapping table names alone is safe has passed native acceptance.

## References

- [UnrealReZen source](https://github.com/rm-NoobInCoding/UnrealReZen), used for initial archive identity/directory construction.
- [CUE4Parse container-header reader](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/IO/Objects/FIoContainerHeader.cs), compared with the observed original header.
- [retoc](https://github.com/trumank/retoc), used to extract and repack raw chunks. The inspected local fork's container-header code also records a Rebirth-specific extra field.
- [Rebirth texture container writer](https://github.com/masonpetrosky/FF7RebirthMods/blob/main/TextureUpscaler/rebirthtex/iostore_writer.py), inspected for the game's legacy TOC and hash format.
- [Rebirth mesh container-header reader](https://github.com/nikolaybutnik/FFVII-Rebirth-Mesh-Patcher/blob/main/lib/conheader.py), inspected for package-store layout and preservation requirements.

All original assets, crash dumps, generated archives, raw captures and local machine paths remain outside the published source files.
