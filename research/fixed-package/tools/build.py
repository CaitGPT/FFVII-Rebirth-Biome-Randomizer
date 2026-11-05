"""Build a seeded prototype from the user's own raw exports. Defaults to plan-only.

python tools/build.py --config tools/build-config.local.json --seed 44
Add --execute to write and verify the modified table; --pack also packs it.
No command installs the package, launches the game, or writes saves.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
from pathlib import Path
import subprocess
import tempfile

from randomize import load_export, make_plan, sha256, verify_result
from container_check import unpack
from oodle_codec import OodleCodec
from rebirth_container import write_override

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "BiomeRandomizer_P"


def run(args: list, cwd: Path | None = None) -> None:
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(config: dict, seed: str, execute: bool = False, pack: bool = False, only: list[str] | None = None) -> Path:
    if pack and not execute:
        raise ValueError("--pack requires --execute")
    vanilla_root = Path(config["vanilla_root"]).resolve()
    output_root = Path(config.get("build_root", ROOT / "build")).resolve()
    # Never permit staging/export output to land over the original game data.
    if output_root.is_relative_to(vanilla_root) or vanilla_root.is_relative_to(output_root):
        raise ValueError("Build and original export roots must be separate")
    catalog_path = ROOT / "data" / "pools.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    inputs = {}
    for role, asset in catalog["assets"].items():
        path = vanilla_root / "End" / "Content" / asset["path"]
        if sha256(path) != asset["sha256"]:
            raise ValueError(f"Unreviewed vanilla asset hash: {role}. Re-investigate this game version first.")
        inputs[role] = path
    builder_project = ROOT / "tools" / "DataBuilder" / "DataBuilder.csproj"
    run(["dotnet", "build", builder_project, "-c", "Release", "--nologo", "-v", "quiet"])
    builder = builder_project.parent / "bin" / "Release" / "net8.0" / "TrainingDummy.DataBuilder.dll"
    output_root.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="seed-", dir=output_root))
    for role, path in inputs.items():
        run(["dotnet", builder, "export", path, output / f"{role}.csv"])
    before = load_export(output / "territory.csv")
    spec, audit = make_plan(catalog, before, load_export(output / "mob.csv"),
                            load_export(output / "battle.csv"), load_export(output / "character.csv"), seed, only)
    audit["inputs"] = {role: {"asset": catalog["assets"][role]["path"], "sha256": sha256(path)} for role, path in inputs.items()}
    audit["catalog_sha256"] = sha256(catalog_path)
    audit["mode"] = "plan"
    write_json(output / "spec.json", spec)
    write_json(output / "audit.json", audit)
    if execute:
        staging = output / "staging"
        run(["dotnet", builder, "build", output / "spec.json", vanilla_root, staging])
        modified = staging / "End" / "Content" / catalog["assets"]["territory"]["path"]
        run(["dotnet", builder, "export", modified, output / "result.csv"])
        verify_result(before, load_export(output / "result.csv"), spec)
        audit["mode"] = "table_verified"
        audit["modified_asset_sha256"] = sha256(modified)
        if pack:
            packager = Path(config["packager"]).resolve()
            paks = Path(config["game_root"]).resolve() / "End" / "Content" / "Paks"
            # ReZen recursively scans --game-dir, including installed mods. An
            # earlier BiomeRandomizer override then becomes a second source of
            # the same chunk ID. Give it only top-level vanilla archives through
            # read-only use of hard links, without moving any installed files.
            archive_view = output / "archive-input"
            archive_view.mkdir()
            for archive in sorted(paks.iterdir()):
                if archive.is_file() and archive.suffix.lower() in (".pak", ".utoc", ".ucas"):
                    try:
                        os.link(archive, archive_view / archive.name)
                    except OSError as error:
                        raise ValueError("Set build_root to a writable directory on the game's volume; archive hard links require the same volume") from error
            if not any(archive_view.glob("*.utoc")):
                raise ValueError("No original IoStore archives found in the game's Paks directory")
            package_dir = output / "package"
            package_dir.mkdir()
            run([packager, "--content-path", staging, "--compression-format", "Zlib",
                 "--engine-version", "GAME_UE4_26", "--game-dir", archive_view,
                 "--output-path", package_dir / f"{PACKAGE}.utoc"], cwd=packager.parent)
            # Never overwrite UCAS bytes with a guessed header: its first bytes
            # are compressed chunk data, not a universal game-file preamble.
            intermediate = package_dir / PACKAGE
            toc = intermediate.with_suffix(".utoc").read_bytes()
            chunks = unpack(toc, intermediate.with_suffix(".ucas").read_bytes())
            exports = [identity for identity in chunks if identity[-1] == 2]
            headers = [identity for identity in chunks if identity[-1] == 10]
            if len(exports) != 1 or len(headers) != 1:
                raise ValueError("Expected one asset and one header before Rebirth metadata repair")
            codec = OodleCodec(Path(config.get("oodle", packager.parent / "oo2core_9_win64.dll")))
            corrected = output / "package-corrected"
            corrected.mkdir()
            audit["container_verification"] = write_override(corrected / PACKAGE,toc,modified,codec)
            shutil.copyfile(package_dir / f"{PACKAGE}.pak", corrected / f"{PACKAGE}.pak")
            package_dir = corrected
            audit["package_directory"] = "package-corrected"
            audit["rebirth_metadata"] = {"declared_packages":0,"header_bytes":65536,"uses_original_game_store":True}
            audit["packager_sha256"] = sha256(packager)
            audit["oodle_sha256"] = sha256(codec.path)
            audit["package"] = [{"name": f"{PACKAGE}{ext}", "sha256": sha256(package_dir / f"{PACKAGE}{ext}"),
                                 "bytes": (package_dir / f"{PACKAGE}{ext}").stat().st_size} for ext in (".pak", ".ucas", ".utoc")]
            audit["mode"] = "packed_unvalidated"
        # Verify the original exports still match the recorded inputs.
        if any(sha256(inputs[role]) != info["sha256"] for role, info in audit["inputs"].items()):
            raise ValueError("Original asset changed during build")
        write_json(output / "audit.json", audit)
    print(json.dumps({"output": str(output), "mode": audit["mode"], "seed": seed,
                      "changed": audit["changed_count"], "native_validation": "pending"}))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--pack", action="store_true")
    parser.add_argument("--only", nargs="+")
    args = parser.parse_args()
    build(json.loads(args.config.read_text(encoding="utf-8-sig")), args.seed, args.execute, args.pack, args.only)
