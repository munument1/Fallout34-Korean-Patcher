"""Audit FO4/TMR Korean assets for a future unified FO4+FO3+FNV installer.

Read-only: produces a JSON installation manifest, never generates/copies ESMs,
never writes to Fallout 4/Data or modifies the supplied TMR ZIP.
The TMR release asset is supplied locally; no game binaries are redistributed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
TMR_RELEASE = "v1.0.5"
TMR_SHA256 = "315dee0f12284ca50fe7664ef0595a404404ef478ebd06665a82f9b5fd23ae52"
TMR_BASE = "FO4_AE_1.11.191.Kor"
ASSET_FOLDERS = {"strings", "interface", "programs"}
STRINGS_NAME = re.compile(r"(?i)^(?P<stem>.+)_(?P<language>en|ko)\.(?P<kind>DLSTRINGS|ILSTRINGS|STRINGS)$")
HANGUL = re.compile(r"[\uac00-\ud7a3]")
GAMES = {"fo3": "Fallout34.esm", "fnv": "FalloutNV34.esm"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def iter_assets(source: Path):
    """Read a local MO2 resource folder directly, or an optional TMR release ZIP."""
    if source.is_dir():
        root = source.resolve()
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError(f"Unsafe linked source file: {path}")
            yield TMR_BASE + "/" + path.relative_to(source).as_posix(), path.read_bytes()
    else:
        with ZipFile(source) as z:
            for member in z.infolist():
                if not member.is_dir():
                    yield member.filename, z.read(member)


def inspect(zip_path: Path, data_dir: Path, check_pin: bool = True) -> dict:
    is_local_folder = zip_path.is_dir()
    actual_sha = None if is_local_folder else digest(zip_path)
    if check_pin and not is_local_folder and actual_sha != TMR_SHA256:
        raise ValueError("TMR release SHA256 differs from verified v1.0.5 asset")
    entries = {}
    cc_languages = defaultdict(dict)
    for source_name, payload in iter_assets(zip_path):
            parts = PurePosixPath(source_name).parts
            if not parts or any(x in ("", ".", "..") for x in parts):
                raise ValueError(f"Unsafe source entry: {source_name}")
            if TMR_BASE not in parts:
                continue
            index = parts.index(TMR_BASE)
            relative_parts = parts[index + 1:]
            if len(relative_parts) < 2 or relative_parts[0].casefold() not in ASSET_FOLDERS:
                continue
            relative = "/".join(relative_parts)
            if relative.casefold() in entries:
                raise ValueError(f"Duplicate case-insensitive target: {relative}")
            item = {
                "source_member": source_name,
                "relative_data_path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
            matched = STRINGS_NAME.fullmatch(relative_parts[-1])
            if relative_parts[0].casefold() == "strings" and matched and matched["stem"].casefold().startswith("cc"):
                # FO4 launched in English loads *_en tables; Korean-only CC
                # sidecars must map to the English filename to be effective.
                normalized = ("Strings/" + matched["stem"] + "_en." + matched["kind"])
                item["relative_data_path"] = normalized
                item["cc_language_source"] = matched["language"].casefold()
                item["hangul_count"] = len(HANGUL.findall(payload.decode("utf-8", "ignore")))
                cc_languages[normalized.casefold()][matched["language"].casefold()] = item
            else:
                entries[relative.casefold()] = item

    decisions = Counter()
    conflicts = []
    for key, options in sorted(cc_languages.items()):
        en, ko = options.get("en"), options.get("ko")
        if en and ko:
            # FO4 running in English reads *_en tables. Never replace the
            # existing _en data with a different _ko variant on a heuristic:
            # translation completeness and string-ID parity require review.
            chosen, rule = en, "en_kept_ko_variant_review"
            if en["sha256"] != ko["sha256"]:
                conflicts.append({
                    "target": chosen["relative_data_path"],
                    "en_hangul": en["hangul_count"],
                    "ko_hangul": ko["hangul_count"],
                    "selected": "en",
                    "review_required": True,
                })
        elif ko:
            chosen, rule = ko, "ko_only_remapped_to_en"
        else:
            chosen, rule = en, "en_only"
        assert chosen
        item = dict(chosen)
        item.pop("hangul_count", None)
        item["mapping_reason"] = rule
        if key in entries:
            raise ValueError(f"Duplicate output asset: {key}")
        entries[key] = item
        decisions[rule] += 1

    required = {"interface/fontconfig.txt", "interface/fonts_en.swf",
                "strings/fallout4_en.strings", "strings/fallout4_en.dlstrings",
                "strings/fallout4_en.ilstrings"}
    missing = sorted(required - entries.keys())
    if missing:
        raise RuntimeError(f"Incomplete TMR base Korean assets: {missing}")

    source_esms = {}
    for game, name in GAMES.items():
        report = json.loads((ROOT / "data" / game / "indexed_plan_report.json").read_text("utf-8"))
        expected = report["esm_sha256"]
        src = data_dir / name
        if not src.is_file():
            raise FileNotFoundError(src)
        observed = digest(src)
        if observed != expected:
            raise RuntimeError(f"{game}: converter ESM differs from pinned revision")
        work_report = json.loads(
            (ROOT / "data" / game / "current_translation_work_report.json").read_text("utf-8")
        )
        source_esms[game] = {
            "filename": name, "sha256": observed,
            "remaining_work_field_occurrences": work_report["translation_work_item_occurrences"],
            "remaining_work_unique_items": work_report["distinct_type_field_english_work_items"],
            "translated_output_ready": False,
        }

    installed_cc = sorted(p.name for p in data_dir.glob("cc*.esl") if p.is_file())
    available_cc = {STRINGS_NAME.fullmatch(Path(i["relative_data_path"]).name)["stem"].casefold()
                    for i in entries.values()
                    if i["relative_data_path"].casefold().startswith("strings/cc")
                    and STRINGS_NAME.fullmatch(Path(i["relative_data_path"]).name)}
    missing_cc = [name for name in installed_cc if Path(name).stem.casefold() not in available_cc]
    planned_existing = sum((data_dir / Path(x["relative_data_path"].replace("/", "\\"))).exists()
                           for x in entries.values())
    assets = sorted(entries.values(), key=lambda x: x["relative_data_path"].casefold())
    return {
        "schema_version": 1,
        "status": "source_assets_inventoried_NOT_INSTALLABLE_YET",
        "tmr_release": TMR_RELEASE, "tmr_zip_sha256": actual_sha,
        "source_kind": "installed_mo2_folder" if is_local_folder else "verified_release_zip",
        "source_location": str(zip_path.resolve()),
        "tmr_repository": "https://github.com/munument1/The-Midnight-Ride-KR-Patcher",
        "translation_source": TMR_BASE,
        "game_data_dir_for_local_checks": str(data_dir),
        "asset_count": len(assets),
        "asset_groups": dict(Counter(x["relative_data_path"].split("/")[0] for x in assets)),
        "cc_source_mapping": dict(decisions),
        "cc_variant_files_with_different_payloads": len(conflicts),
        "cc_variant_examples": conflicts[:15],
        "installed_cc_plugin_count": len(installed_cc),
        "installed_cc_plugins_without_tmr_string_tables": missing_cc,
        "possible_existing_data_file_collisions": planned_existing,
        "converted_esms": source_esms,
        "asset_files": assets,
        "warnings": [
            "TMR CC coverage concerns localized STRING tables only; nonlocalized CC plugin text requires separate review.",
            "The source contains a mix of *_en and *_ko tables. CC *_ko-only entries are mapped to *_en paths; conflicting pairs stay on *_en and require review.",
            "Do not install until FO3 and FNV work candidates are resolved and translated ESM output passes independent QA.",
            "The original game/Data, online plugins, BA2/ESL resource carriers, and source Korean patch folder/ZIP were not modified.",
            "Runtime text, glyph coverage, and language settings require in-game testing.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--fo4-korean-dir", type=Path, help="MO2 FO4_AE_1.11.191.Kor folder")
    src.add_argument("--tmr-zip", type=Path, help="legacy pinned release ZIP")
    parser.add_argument("--game-data", type=Path, default=Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data"))
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "unified_installer" / "source_manifest.json")
    parser.add_argument("--allow-unpinned-tmr", action="store_true", help="tests only")
    args = parser.parse_args()
    source = args.fo4_korean_dir or args.tmr_zip
    result = inspect(source, args.game_data, not args.allow_unpinned_tmr)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: result[k] for k in (
        "status", "source_kind", "source_location", "asset_count", "asset_groups", "cc_source_mapping",
        "cc_variant_files_with_different_payloads", "installed_cc_plugin_count",
        "installed_cc_plugins_without_tmr_string_tables", "converted_esms",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
