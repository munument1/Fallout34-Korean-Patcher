r"""Build a MO2-ready combined Korean patch, only after the FO3/FNV translation is ready.

The checked-in FO4/DLC/CC translation and Korean font resources are staged from
assets/fo4_korean. FO3/FNV localized ESMs are user-produced locally, NEVER
bundled in GitHub. Incomplete translations abort before creating any output.

Usage when both conversions are actually complete:
 python tools/build_unified_install_output.py --game-data "C:\...\Fallout 4\Data" ^
   --fo3-translated "...\Fallout34.esm" --fnv-translated "...\FalloutNV34.esm" ^
   --output "D:\Fallout34-Korean-Output"

For now:
 python tools/build_unified_install_output.py --inspect
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from audit_unified_install_sources import inspect as inspect_fo4_assets, GAMES
from build_localized_esm_copy import load_assignments
from verify_localized_esm_copy import verify as verify_translated_esm
from verify_current_esm_translation_plan import EXTRAS, MIGRATED_EXTRAS

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "assets" / "fo4_korean"
INDEX = ROOT / "assets" / "fo4_korean_sources.json"
MOD_NAME = "Fallout34 Unified Korean"
DEFAULT_GAME_DATA = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def local_inventory(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): sha256(p)
        for p in folder.rglob("*")
        if p.is_file()
    }


def check_bundled() -> dict:
    if not INDEX.is_file():
        raise RuntimeError("Bundled FO4 Korean index missing")
    reference = json.loads(INDEX.read_text("utf-8"))
    observed = local_inventory(BUNDLED)
    if observed != reference["files"]:
        missing = sorted(reference["files"].keys() - observed.keys())
        extra = sorted(observed.keys() - reference["files"].keys())
        altered = sorted(x for x in observed.keys() & reference["files"].keys()
                         if observed[x] != reference["files"][x])
        raise RuntimeError(f"Bundled FO4 Korean data mismatch: missing={missing[:4]}, extra={extra[:4]}, altered={altered[:4]}")
    return reference


def review(game: str) -> dict:
    folder = ROOT / "data" / game
    report = json.loads((folder / "current_translation_work_report.json").read_text("utf-8"))
    return {
        "work_field_occurrences": report["translation_work_item_occurrences"],
        "work_unique_entries": report["distinct_type_field_english_work_items"],
    }


def preflight(game_data: Path, translated: dict[str, Path] | None = None) -> dict:
    assets = check_bundled()
    original = inspect_fo4_assets(BUNDLED, game_data)
    remaining = {game: review(game) for game in GAMES}
    ready = all(row["work_field_occurrences"] == 0 for row in remaining.values())
    if translated is None or set(translated) != set(GAMES):
        ready = False
    else:
        for game, src in translated.items():
            if not src.is_file() or src.resolve() == (game_data / GAMES[game]).resolve():
                ready = False
    return {
        "version": 1,
        "source": "bundled:assets/fo4_korean",
        "bundled_files": len(assets["files"]),
        "output_fo4_assets": original["asset_count"],
        "installed_cc_plugins": original["installed_cc_plugin_count"],
        "cc_files_different_en_ko": original["cc_variant_files_with_different_payloads"],
        "cc_review_required": original["cc_variant_files_with_different_payloads"] > 0,
        "remaining": remaining,
        "ready_to_build": ready,
        "warning": "Preflight is not evidence of complete runtime translation. Install is blocked when translation work is incomplete.",
    }


def _safe_relative(value: str) -> Path:
    path = Path(value.replace("/", "\\"))
    if not value or path.is_absolute() or ".." in path.parts or ":" in value:
        raise ValueError(f"Unsafe output path: {value}")
    return path


def create(game_data: Path, output: Path, translated: dict[str, Path]) -> dict:
    game_data = game_data.resolve()
    output = output.resolve()
    source = BUNDLED.resolve()
    # Guard against writing the game directory, a parent of it, the checkout,
    # or a parent of the Korean resource bundle.
    for protected in (game_data, ROOT.resolve(), source):
        if output == protected or output in protected.parents or protected in output.parents:
            raise ValueError(f"Output overlaps protected path: {protected}")
    if output.exists():
        raise FileExistsError(output)
    inspection = preflight(game_data, translated)
    if not inspection["ready_to_build"]:
        raise RuntimeError("FO3/FNV Korean translation still incomplete; no output produced")

    for game, localized in translated.items():
        if localized.resolve() == (game_data / GAMES[game]).resolve():
            raise ValueError(f"Never overwrite installed {GAMES[game]}")
        folder = ROOT / "data" / game
        all_plan_files = [folder / p for p in (*EXTRAS, *MIGRATED_EXTRAS[game])]
        assignments, _ = load_assignments(folder, all_plan_files)
        # Independently verify that the supplied translated ESM changed only
        # permitted strings, including exact FormID, group and subrecord layout.
        verify_translated_esm(game_data / GAMES[game], localized, assignments)

    asset_info = inspect_fo4_assets(BUNDLED, game_data)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=".fallout34-ko-", dir=output.parent))
    success = False
    try:
        stage = tmp / "mods" / MOD_NAME
        checked = 0
        for item in asset_info["asset_files"]:
            rel = _safe_relative(item["relative_data_path"])
            target = (stage / rel).resolve()
            if stage.resolve() not in target.parents:
                raise ValueError("Asset escapes MO2 mod root")
            # For local folder source, source_member is a logical bundle key.
            raw_relative = Path(item["source_member"])
            if raw_relative.parts[0] != "FO4_AE_1.11.191.Kor":
                raise RuntimeError("Unexpected FO4 source root")
            path = BUNDLED.joinpath(*raw_relative.parts[1:])
            if sha256(path) != item["sha256"]:
                raise RuntimeError(f"Bundled source asset changed: {path}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            checked += 1
        for game, esm in translated.items():
            target = stage / GAMES[game]
            shutil.copy2(esm, target)
            if sha256(target) != sha256(esm):
                raise RuntimeError(f"Copied {game} Korean ESM hash differs")
        report = {
            "mod": MOD_NAME,
            "fo4_assets": checked,
            "converted_esms": {game: {"filename": GAMES[game], "sha256": sha256(source)}
                               for game, source in translated.items()},
            "pending_cc_variant_review": asset_info["cc_variant_files_with_different_payloads"],
            "disclaimer": "MO2 staging output only. No original Data directory or online mod modified.",
        }
        (tmp / "fallout34-unified-korean-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.rename(output)
        success = True
        return report
    finally:
        if not success and tmp.exists():
            shutil.rmtree(tmp)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-data", type=Path, default=DEFAULT_GAME_DATA)
    parser.add_argument("--fo3-translated", type=Path)
    parser.add_argument("--fnv-translated", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(preflight(args.game_data), ensure_ascii=False, indent=2))
        return
    if not (args.fo3_translated and args.fnv_translated and args.output):
        parser.error("Combined output requires --fo3-translated, --fnv-translated and --output")
    translated = {"fo3": args.fo3_translated, "fnv": args.fnv_translated}
    print(json.dumps(create(args.game_data, args.output, translated), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
