"""Recover localized fields when Fallout34 changes the source record schema.

Read-only inputs:
 - Fallout 4/Data/F34/Fallout( NV )34_import.json (converter's exact FormID map)
 - Fallout 3/New Vegas original ESM + DLC master records
 - source plugin's xTranslator Korean SST dictionaries
 - installed, SHA256-pinned converted ESM and existing extraction/translation plans

This intentionally compares *source* type/field with *target* type/field as
independent dimensions. We require the converter's exact source-plugin/local-ID
-> converted FormID link, the original source ESM's exact string on a record
owned by that original plugin, and a matching Korean SST entry attached to that
same original record+field. Only an unambiguous Korean can be reused.

Writes ONLY new JSONL translation plans and unresolved review evidence; no
plugin, ESM copy, online mod or game assets are modified or generated.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FO4_DATA = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
SST_DIR = Path("F:/번역/프로그램/xTranslator/UserDictionaries/FalloutNV")
GAMES = {
    "fo3": {
        "import": "Fallout34_import.json",
        "esm": "Fallout34.esm",
        "original": Path(r"C:\Games\Steam\steamapps\common\Fallout 3 goty\Data"),
        "plugins": ("fallout3", "anchorage", "thepitt", "brokensteel", "pointlookout", "zeta"),
    },
    "fnv": {
        "import": "FalloutNV34_import.json",
        "esm": "FalloutNV34.esm",
        "original": Path(r"C:\Games\Steam\steamapps\common\Fallout New Vegas\Data"),
        "plugins": ("falloutnv", "deadmoney", "honesthearts", "oldworldblues",
                    "lonesomeroad", "gunrunnersarsenal", "caravanpack",
                    "classicpack", "mercenarypack", "tribalpack"),
    },
}
ACTIVE_PLANS = (
    "indexed_patch_plan_candidates.jsonl.gz",
    "indexed_patch_plan_v2_strict_extra.jsonl.gz",
    "xtranslator_verified_visible_extra.jsonl.gz",
    "manual_visible_translation_verified.jsonl.gz",
    "sibling_info_field_verified.jsonl.gz",
)
# Avoid automatic changes to unknown runtime/internal fields.
DISPLAY_FIELD = {
    ("INFO", "NAM1"), ("INFO", "RNAM"),
    ("TERM", "FULL"), ("TERM", "ITXT"), ("TERM", "BTXT"),
    ("TERM", "UNAM"), ("TERM", "RNAM"),
    ("NOTE", "FULL"), ("NOTE", "DESC"),
    ("MESG", "FULL"), ("MESG", "DESC"), ("MESG", "ITXT"),
    ("QUST", "CNAM"),
    ("BOOK", "FULL"), ("BOOK", "DESC"),
    ("NPC_", "FULL"), ("ARMO", "FULL"), ("WEAP", "FULL"),
    ("MISC", "FULL"), ("KEYM", "FULL"), ("ALCH", "FULL"),
    ("AMMO", "FULL"), ("PERK", "FULL"), ("PERK", "DESC"),
    ("CELL", "FULL"), ("WRLD", "FULL"),
    ("CONT", "FULL"), ("ACTI", "FULL"), ("DOOR", "FULL"),
    ("FURN", "FULL"),
}
EDIT_CUE = re.compile(r"^\s*(?:\{[^{}\r\n]{1,160}\}\s*)+")
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)


def gz_rows(path):
    with gzip.open(path, "rt", encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)


def write_rows(path, rows):
    with gzip.open(path, "wt", encoding="utf8", compresslevel=6) as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha(path):
    d = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(8 * 1024 * 1024), b""):
            d.update(block)
    return d.hexdigest()


def load_sst_parser():
    spec = importlib.util.spec_from_file_location(
        "source_sst_reader_for_manifest", ROOT / "tools" / "read_xtranslator_sst.py"
    )
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def source_record_parser():
    # FNV has the same 24-byte record header and XXXX field framing. Its
    # parser already filters out master overrides by TES4 master-list index.
    spec = importlib.util.spec_from_file_location(
        "original_esm_parser_for_manifest", ROOT / "tools" / "recover_fnv_xtranslator_origin_verified.py"
    )
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    return parser


def active_key(row):
    return (
        row["target_formid"].upper(),
        row["record_type"], row["field"],
        int(row["target_field_occurrence_index"]),
    )


def run(game):
    cfg = GAMES[game]
    folder = ROOT / "data" / game
    target = FO4_DATA / cfg["esm"]
    expected = json.loads((folder / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if sha(target) != expected:
        raise RuntimeError("Converter target ESM is different from the pinned audit snapshot")
    manifest_path = FO4_DATA / "F34" / cfg["import"]
    manifest = json.loads(manifest_path.read_text("utf8"))
    if manifest.get("plugin", "").casefold() != cfg["esm"].casefold():
        raise ValueError("Converter manifest plugin does not match target ESM")

    # Only accept named source master ESMs actually installed locally.
    allowed_plugins = {x + ".esm" for x in cfg["plugins"]}
    origin_for_target = defaultdict(set)
    for source_key, record in manifest["forms"].items():
        if "|" not in source_key or not isinstance(record, list) or len(record) != 2:
            continue
        src_plugin, source_id = source_key.lower().rsplit("|", 1)
        if src_plugin not in allowed_plugins or not re.fullmatch(r"[0-9a-f]{6}", source_id):
            continue
        target_type, number = record
        if not isinstance(target_type, str) or not isinstance(number, int):
            continue
        origin_for_target[f"{number:08X}"].add((src_plugin, int(source_id, 16), target_type))

    planned = {}
    for name in ACTIVE_PLANS:
        for row in gz_rows(folder / name):
            key = active_key(row)
            value = row["english"], row["korean"]
            if key in planned and planned[key] != value:
                raise ValueError(f"Overlapping translation plans conflict {key}")
            planned[key] = value
    residual = {}
    by_orig_id = defaultdict(set)
    direct_origins = {}
    stats = Counter()
    for row in gz_rows(folder / "xtranslator_residual_candidates.jsonl.gz"):
        if row["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        if (row["record_type"], row["field"]) not in DISPLAY_FIELD:
            continue
        if row.get("conditional_proc") is not None:
            continue
        if not row["english"] or not row["english"].strip():
            continue
        key = row["formid"].upper(), row["record_type"], row["field"], int(row["index"])
        if key in planned:
            continue
        if key in residual:
            raise ValueError(f"Duplicate residual {key}")
        sources = [
            (plugin, local) for plugin, local, record_type in origin_for_target.get(key[0], ())
            if record_type == key[1]
        ]
        if not sources:
            continue
        residual[key] = row
        direct_origins[key] = sources
        for plugin, local in sources:
            by_orig_id[plugin].add(local)
        stats["mapped_unlinked_fields"] += 1

    reader = load_sst_parser()
    orig_parser = source_record_parser()
    sst_by_origin = defaultdict(set)
    sst_sha = {}
    for name in cfg["plugins"]:
        path = SST_DIR / (name + "_en_ko.sst")
        if not path.is_file():
            continue
        parsed = reader.parse_sst(path)
        sst_sha[path.name] = parsed["sha256"]
        masters = [x.lower() for x in parsed["master_files"]]
        for row in parsed["records"]:
            num = int(row["form_id"], 16)
            if num >> 24 >= len(masters):
                continue
            plugin = masters[num >> 24]
            local = num & 0xFFFFFF
            if plugin not in by_orig_id or local not in by_orig_id[plugin]:
                continue
            if not row["korean"] or row["korean"] == row["source"]:
                continue
            identifier = plugin, local, row["record_name"], row["field_name"], row["source"]
            sst_by_origin[identifier].add((row["korean"], path.name, int(row["index"])))

    original = {}
    orig_sha = {}
    for plugin, ids in by_orig_id.items():
        p = cfg["original"] / plugin
        if not p.is_file():
            raise FileNotFoundError(p)
        owner = orig_parser.original_owner_index(p)
        seen = set()
        for fid, typ, fields in orig_parser.esm_records(p, ids, owner_index=owner):
            local = fid & 0xFFFFFF
            if local in seen:
                raise RuntimeError(f"Original owner ESM has duplicate ID {plugin}:{local:06X}")
            seen.add(local)
            original[(plugin, local)] = typ, fields
        orig_sha[plugin] = sha(p)
    rows, review = [], []
    for key, row in residual.items():
        target_text = row["english"]
        translations = defaultdict(set)
        rejections = Counter()
        for plugin, local in direct_origins[key]:
            source = original.get((plugin, local))
            if not source:
                rejections["original_source_record_not_found"] += 1
                continue
            source_type, source_fields = source
            for (src_field, src_index), original_text in source_fields.items():
                if original_text is None:
                    continue
                if original_text == target_text:
                    transformed = "exact_original_text"
                elif EDIT_CUE.match(original_text) and EDIT_CUE.sub("", original_text).strip() == target_text:
                    transformed = "converter_removed_editor_cue"
                else:
                    continue
                exact = (
                    plugin, local, source_type, src_field, original_text
                )
                candidates = sst_by_origin.get(exact, set())
                if not candidates:
                    rejections["source_record_field_not_in_korean_sst"] += 1
                for korean, sst_name, sst_index in candidates:
                    if not korean.strip() or "\ufffd" in korean or korean == target_text:
                        rejections["translation_invalid"] += 1
                        continue
                    if Counter(TOKEN.findall(target_text)) != Counter(TOKEN.findall(korean)):
                        rejections["protected_token_mismatch"] += 1
                        continue
                    if transformed == "converter_removed_editor_cue" and EDIT_CUE.match(korean):
                        rejections["korean_editor_cue_not_removed"] += 1
                        continue
                    proof = (
                        plugin, local, source_type, src_field, src_index,
                        sst_name, sst_index, transformed,
                    )
                    translations[korean].add(proof)
        if not translations:
            reason = "no_same_source_proven_korean"
        elif len(translations) > 1:
            reason = "conflicting_source_translations"
        else:
            reason = "manifest_source_esm_sst_verified"
        stats[reason] += 1
        if reason == "manifest_source_esm_sst_verified":
            korean, proof_set = next(iter(translations.items()))
            entry = {
                "target_formid": key[0],
                "record_type": key[1],
                "field": key[2],
                "target_field_occurrence_index": key[3],
                "english": target_text,
                "korean": korean,
                "plan_source": "fallout34_converter_import_original_esm_sst_migrated",
                "previous_unlinked_class": row["status"],
                "source_evidence": [
                    {"source_plugin": plugin, "source_local_formid": f"{local:06X}",
                     "original_record_type": src_type, "original_field": src_field,
                     "original_field_index": src_index, "sst_file": sst_name,
                     "sst_index": sst_index, "text_transform": transform}
                    for plugin, local, src_type, src_field, src_index, sst_name, sst_index, transform
                    in sorted(proof_set)
                ],
            }
            rows.append(entry)
            stats["restored_" + row["status"]] += 1
            stats[f"type_field_{entry['source_evidence'][0]['original_record_type']}/{entry['source_evidence'][0]['original_field']}_to_{key[1]}/{key[2]}"] += 1
        else:
            review.append({
                "target_formid": key[0], "target_record_type": key[1], "target_field": key[2],
                "target_field_occurrence_index": key[3], "english": target_text,
                "unlinked_status": row["status"], "reason": reason,
                "source_origins": [f"{plugin}:{local:06X}" for plugin, local in direct_origins[key]],
                "original_search_failures": dict(rejections),
                "suggested_korean": list(translations.keys())[:3],
            })
    # Independent check that source/target FormID, record type, field index and
    # English still exist exactly on the installed target ESM.
    by_fid = defaultdict(list)
    for row in rows:
        by_fid[int(row["target_formid"], 16)].append(row)
    verified, unresolved = [], []
    seen = set()
    for fid, typ, fields in orig_parser.esm_records(target, set(by_fid)):
        if fid in seen:
            raise RuntimeError(f"Duplicate converted FormID {fid:08X}")
        seen.add(fid)
        for row in by_fid[fid]:
            if typ == row["record_type"] and fields.get(
                (row["field"], row["target_field_occurrence_index"])
            ) == row["english"]:
                verified.append(row)
            else:
                unresolved.append({**row, "reason": "target_field_mismatch_after_converter"})
    for fid in set(by_fid) - seen:
        unresolved.extend({**row, "reason": "target_formid_not_found"} for row in by_fid[fid])
    if unresolved:
        raise RuntimeError(f"{len(unresolved)} target fields failed independent verification")
    if sha(target) != expected:
        raise RuntimeError("Converted ESM changed during verification")
    verified.sort(key=active_key)
    write_rows(folder / "import_manifest_migrated_verified.jsonl.gz", verified)
    write_rows(folder / "import_manifest_migrated_review.jsonl.gz", review)
    summary = {
        "game": game,
        "converted_esm_sha256": expected,
        "converter_import_manifest_sha256": sha(manifest_path),
        "original_esm_hashes": orig_sha,
        "sst_hashes": sst_sha,
        "converter_form_links": len(manifest["forms"]),
        "candidate_fields_after_current_plan": len(residual),
        "verified_new_translations": len(verified),
        "status_counts": {k: v for k, v in stats.items() if not k.startswith("type_field_")},
        "migration_type_field_counts": {
            k.removeprefix("type_field_"): v for k, v in stats.items()
            if k.startswith("type_field_")
        },
        "needs_review": len(review),
        "scope": "Source plugin record provenance confirmed by converter's own import manifest, original ESM, and Korean SST; converted target bytes verified. No game ESM edited.",
    }
    (folder / "import_manifest_migrated_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(game, "MAPPED", len(residual), "RECOVERED", len(verified),
          "STILL_REVIEW", len(review), "MIGRATIONS", Counter(
              (r["source_evidence"][0]["original_record_type"],
               r["source_evidence"][0]["original_field"],
               r["record_type"], r["field"]) for r in verified).most_common(20),
          flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("game", choices=GAMES)
    run(parser.parse_args().game)
