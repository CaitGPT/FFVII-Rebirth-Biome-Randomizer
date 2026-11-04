# Packaging investigation

## Controls and observations

The first build changed one byte in the original regional table: the relative pointer for one existing enemy-template array. Both attempts with that package crashed during Grasslands travel. The same save and destination succeeded after removing only BiomeRandomizer. An override containing the byte-identical original table also crashed. These controls establish that an enemy substitution is not necessary to trigger the failure.

The original table's serializer round-trip reproduced its bytes exactly. The source table and the archive therefore need separate verification.

## Compressed-block corruption

The inherited build recipe overwrote the first ten UCAS bytes with bytes from a vanilla container. In these archives the first bytes belong to a compressed container-header block. Independent decompression failed on that block after the overwrite, while the asset block still decompressed correctly. The build now preserves the packager's block data and decompresses every block during verification.

This recipe came from the owner's [Training Dummy build script](https://github.com/AW1KSwinton/FFVII-Rebirth-Training-Dummy/blob/main/tools/Build-TrainingDummy.ps1). Training Dummy's previously observed native behavior is separate evidence; this investigation does not claim that it cannot work. No installed Training Dummy files were changed.

## Duplicate chunks during rebuilds

The packager scans its game directory recursively. Including an installed BiomeRandomizer override produced duplicate chunk IDs in a subsequent build. The independent verifier refused that archive. Packaging now reads a view containing hard links to top-level vanilla archives, excluding installed mod subdirectories. It does not move or modify those original archives.

The build directory must be on the game's volume for these hard links. A permissions failure also prevents creating them; use normal native file access when running through a sandbox. They are source archive aliases, never outputs that a tool may edit.

## Missing Rebirth package-store metadata

The generic packager produced a container header declaring zero packages. Removing the corrupt byte overwrite alone produced a different failed startup; it did not establish game compatibility.

The original container's decoded header has an additional 32-bit field before its name batch. Its package-store records use 32-byte entries. The selected table's record identifies one export, one bundle, its original size flags and load order, and zero imported packages. These values are read from the original container, not guessed from the filename.

The corrected archive preserves only that selected package's entry and imports. It rebuilds the legacy header with the Rebirth layout, repacks the two raw chunks with retoc, preserves the container ID consistently, and independently verifies the table bytes and metadata again. Synthetic tests also exercise import relocation and refusal of invalid original metadata.

The raw packed control still requires native load and travel acceptance. A syntactically readable archive is not proof that the game accepts it.

## References

- [UnrealReZen source](https://github.com/rm-NoobInCoding/UnrealReZen), used for initial archive identity/directory construction.
- [CUE4Parse container-header reader](https://github.com/FabianFG/CUE4Parse/blob/master/CUE4Parse/UE4/IO/Objects/FIoContainerHeader.cs), compared with the observed original header.
- [retoc](https://github.com/trumank/retoc), used to extract and repack raw chunks. The inspected local fork's container-header code also records a Rebirth-specific extra field.

All original assets, crash dumps, generated archives, raw captures and local machine paths remain outside the published source files.
