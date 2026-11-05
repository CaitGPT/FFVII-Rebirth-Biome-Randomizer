"""Build the player zip from the release DLL and the runtime scripts, laid out to extract into the game folder.

usage: python tools/make_release.py <version> [--installed <game ue4ss Mods folder>]

With --installed, every file must match the copy installed in the game, the one that was tested.
Prints the zip's SHA-256 and every file's, for the release notes.
"""
import argparse, hashlib, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD = "BiomeRandomizerRuntime"
INSIDE = f"End/Binaries/Win64/ue4ss/Mods/{MOD}"
SCRIPTS = ["main", "automatic", "lifecycle", "state_store", "biome_json", "world_pools", "config"]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("version"); ap.add_argument("--installed", type=Path)
    args = ap.parse_args()
    files = [(ROOT / "build/runtime-release/Release/main.dll", "dlls/main.dll")]
    files += [(ROOT / f"runtime/Scripts/{n}.lua", f"Scripts/{n}.lua") for n in SCRIPTS]
    out = ROOT / "build" / f"FFVII-Rebirth-Biome-Randomizer-{args.version}.zip"
    rows = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for source, inside in files:
            data = source.read_bytes()
            if args.installed and (args.installed / MOD / inside).read_bytes() != data:
                raise SystemExit(f"{inside} differs from the installed, tested copy")
            z.writestr(f"{INSIDE}/{inside}", data); rows.append((inside, sha(data)))
        # UE4SS starts a mod whose folder holds enabled.txt, so nobody has to edit mods.txt.
        z.writestr(f"{INSIDE}/enabled.txt", b""); rows.append(("enabled.txt", sha(b"")))
        z.writestr("BiomeRandomizer-README.txt", (ROOT / "build/zip-readme.txt").read_bytes())
        z.writestr("BiomeRandomizer-LICENSE.txt", (ROOT / "LICENSE").read_bytes())
    print(out, sha(out.read_bytes()))
    for inside, digest in rows:
        print(f"  {digest}  {inside}")


if __name__ == "__main__":
    main()
