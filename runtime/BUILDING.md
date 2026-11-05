# Building the pinned runtime

The DLL is built for the tested UE4SS 3.0.1 Beta #0 `c0a8d4c` ABI. Do not substitute the latest headers or loader. The original game table is checked independently at runtime; passing its fingerprint does not prove C++ loader compatibility.

Use Windows x64, Visual Studio Build Tools2022 with the C++ workload, CMake3.22+ and Python3.10+. Run commands in a VS2022 x64 Native Tools prompt, so `dumpbin`, `lib`, `cmake` and `git` are available. Lua fixtures additionally need `lupa` with Lua5.4 support.

## Exact inputs

| Input | Required commit |
| --- | --- |
| [RE-UE4SS source](https://github.com/UE4SS-RE/RE-UE4SS) | `d935b5b23bac03b65c14ae38382b02007204cc2e` |
| Two installed-interface headers from the same repository | `c0a8d4cb259dccb8d7b58aec8b89e51c97222f9b` |
| [UEPseudo](https://github.com/UE4SS-RE/UEPseudo) | `d09b7218bfe7392adeffb500fdeee0b42ca1cd27` |
| [ImGui](https://github.com/ocornut/imgui) | `81160fee56027226bc80b48e196d0332f5541a8c` |
| [ImGuiColorTextEdit](https://github.com/BalazsJako/ImGuiColorTextEdit) | `af7821926251feca84e35f8fa83eee84dae90424` |
| [Zydis](https://github.com/zyantific/zydis), including its pinned Zycore dependency | `569320ad3c4856da13b9dbf1f0d9e20bda63870e` |

UEPseudo required authenticated repository access in the tested setup. Obtain access through its owners; no substitute or private headers are redistributed here. This is a build dependency and an explicit limitation for independent contributors. The historical official template is [UE4SSCPPTemplate](https://github.com/UE4SS-RE/UE4SSCPPTemplate) commit `6631dd796aecbcc1c444f599db6643c0d2f879df`.

Clone these source repositories into your own SDK directory and check out the commits above. Fetch the interface commit into the RE-UE4SS checkout as well. The build script checks each HEAD and tracked source changes. It extracts only `CppUserModBase.hpp` and `StringType.hpp` from the interface commit into the build directory and records their hashes. The exact installed interface is needed because a version label alone did not identify the ABI.

## Import library and build

The tested `UE4SS.dll` has SHA256 `3f5e8d934fe91ff26be2ce3585cef0940d3c73b40295adc09fa6e7b62bc0018f`. The loader itself is a separately installed dependency; this project does not redistribute it. Its public Rebirth distribution has multiple variants, whose exact correspondence to this hash remains a release prerequisite. The standard official zDEV3.0.1 DLL has a different hash and is not a verified replacement.

Generate the import library from the exact installed loader; no pre-existing development folder or checked-in library is required:

```powershell
./tools/make-loader-import.ps1 -Ue4ssDll 'C:/Games/Rebirth/End/Binaries/Win64/ue4ss/UE4SS.dll'
./tools/build-runtime.ps1 `
  -Ue4ssSource 'C:/SDK/RE-UE4SS' `
  -UePseudoSource 'C:/SDK/UEPseudo' `
  -ImGuiSource 'C:/SDK/imgui' `
  -ImGuiTextEditSource 'C:/SDK/ImGuiColorTextEdit' `
  -ZydisSource 'C:/SDK/zydis' `
  -Ue4ssImportLib './build/loader-import/UE4SS.lib'
```

These example paths are placeholders for your own directories. The import tool refuses a different loader hash, inventories its3185 exports, writes a definition file and uses Microsoft's librarian to build the matching x64 import library. Both outputs and their hashes remain in `build/loader-import/`. The build produces `build/runtime-portable/Release/main.dll` and runs the consuming-stack argument regression. It never installs files or starts the game. The existing SDK `TEXT` macro redefinition warning is retained; compilation succeeds.

The repaired native source was successfully compiled through this parameterized recipe with a newly generated import library on2026-11-05. A separate build folder can produce a different PE hash; only the exact installed and natively tested DLL is accepted for a release artifact. Keep its manifest with it.

Run the separate Lua fixtures:

```powershell
python -m unittest discover -s runtime/tests -v
```

Fixtures cannot pass native placement, lifecycle, compatibility, save/load or removal cases. Follow [final QA](../docs/RELEASE-QA.md) before release.
