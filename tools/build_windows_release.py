"""Build a complete, standalone Windows GUI release ZIP.

Build machine: py tools/build_windows_release.py --version v0.1.0-beta.3
Requires PyInstaller on the build machine only. End users do not need Python.
Game ESMs/BA2 and their derived localized copies are never bundled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = "Fallout34-Korean-Patcher"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_release(version: str) -> tuple[Path, str]:
    if not version.startswith("v") or not all(
        char.isalnum() or char in ".-" for char in version
    ):
        raise ValueError("Use a version such as v0.1.0-beta.3")

    sys.path.insert(0, str(ROOT / "tools"))
    from build_mo2_korean_mod import MANIFEST, load_canonical
    from fo4_korean_assets import select_assets

    manifest = json.loads(MANIFEST.read_text("utf-8"))
    if manifest["schema"] != 2:
        raise ValueError("Unsupported canonical dataset")
    for game, meta in manifest["games"].items():
        plan, _ = load_canonical(game, meta)
        print(f"Verified canonical {game}: {len(plan)} entries", flush=True)
    assets = select_assets()
    print(f"Verified FO4 files: {assets['asset_count']} selected", flush=True)

    workspace = ROOT / "work" / "windows_release"
    dist = workspace / "dist"
    stage = dist / PRODUCT
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--onedir", "--windowed", "--noconfirm", "--clean",
        "--name", PRODUCT,
        "--paths", str(ROOT / "tools"),
        "--distpath", str(dist),
        "--workpath", str(workspace / "build"),
        "--specpath", str(workspace),
        str(ROOT / "install_gui.py"),
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    executable = stage / f"{PRODUCT}.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"No packaged executable: {executable}")

    for rel in [
        "assets/fo4_korean",
        "data/canonical",
    ]:
        shutil.copytree(ROOT / rel, stage / rel)
    shutil.copy2(ROOT / "assets/fo4_korean_sources.json",
                 stage / "assets/fo4_korean_sources.json")
    for filename in [
        "README.md",
        "UNIFIED_INSTALLER.md",
        "UPDATED_ESM_COMPATIBILITY.md",
        "UTF8_CONVERSION_HISTORY.md",
        "FONT_REPLACEMENT.md",
    ]:
        shutil.copy2(ROOT / filename, stage / filename)
    (stage / "licenses").mkdir()
    shutil.copy2(ROOT / "licenses/NotoSansKR-OFL.txt",
                 stage / "licenses/NotoSansKR-OFL.txt")
    (stage / "START_HERE.txt").write_text(
        "Fallout34 Korean Patcher - Windows GUI\n"
        "1. Extract this entire ZIP into a normal folder.\n"
        "2. Run Fallout34-Korean-Patcher.exe. Python is NOT required.\n"
        "3. Select the original Fallout34.esm; FalloutNV34.esm in the same "
        "folder is found automatically.\n"
        "4. Choose an EMPTY new output folder destination.\n"
        "5. The result is an MO2 mod folder. Do not overwrite original game ESMs.\n"
        "Never move just the EXE out of this extracted folder; "
        "assets and data must stay beside it.\n"
        "For details read README.md and UPDATED_ESM_COMPATIBILITY.md.\n",
        encoding="utf-8",
    )

    # Every runnable release file stays under this single top-level folder.
    archive = ROOT / "dist" / f"{PRODUCT}-{version}-Windows-x64.zip"
    archive.parent.mkdir(exist_ok=True)
    if archive.exists():
        raise FileExistsError(f"Refusing to overwrite an existing release ZIP: {archive}")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=8, allowZip64=True) as output:
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                output.write(file, arcname=(Path(PRODUCT) / file.relative_to(stage)).as_posix())

    with zipfile.ZipFile(archive, "r") as check:
        bad = check.testzip()
        if bad:
            raise ValueError(f"Corrupt release ZIP entry: {bad}")
        packaged = set(check.namelist())
        required = {
            f"{PRODUCT}/{PRODUCT}.exe",
            f"{PRODUCT}/assets/fo4_korean_sources.json",
            f"{PRODUCT}/data/canonical/manifest.json",
            f"{PRODUCT}/assets/fo4_korean/Interface/fonts_en.swf",
            f"{PRODUCT}/assets/fo4_korean/Programs/fonts_programs.swf",
            f"{PRODUCT}/licenses/NotoSansKR-OFL.txt",
        }
        if not required.issubset(packaged):
            raise ValueError(f"Release ZIP missing files: {required-packaged}")
        if any(name.lower().endswith((".esm", ".esp", ".ba2", ".bsa")) for name in packaged):
            raise ValueError("Release must not contain Bethesda game files")
    checksum = digest(archive)
    (archive.parent / (archive.name + ".sha256")).write_text(
        checksum + "  " + archive.name + "\n", encoding="utf-8")
    print(f"RELEASE={archive}", flush=True)
    print(f"BYTES={archive.stat().st_size}", flush=True)
    print(f"SHA256={checksum}", flush=True)
    return archive, checksum


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    make_release(args.version)
