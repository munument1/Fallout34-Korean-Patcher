"""Reconnect the supplied COMPLETE FO3/FNV Korean SST after FO4 field migrations.

The Fallout34 converter creates hundreds of thousands of new INFO/TERM etc.
fields, so their FormIDs cannot reliably be matched to the original game's
records. A translation can be reliably carried by the *unchanged English* if:

  * every translated original-game SST entry for that English has one Korean;
  * at least one ORIGINAL source ESM record/field at the SST's very same source
    plugin, FormID and index has that exact English;
  * that original record/field is in the expected FO3/FNV->FO4 migration family;
  * the source game and the converted target ESM are pinned by SHA256;
  * the complete target FormID/type/field/index/English is reread byte-exactly,
    and formatting tokens are preserved.

Even with source ESM verification, text-only links are not a proven target
speaker/quest-context identity. All assignments carry that QA qualification.
This program never emits a translated ESM or touches F34Online.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FO4_DATA = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
SST = Path("F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV")
ORIGINAL = {
    "fo3": Path(r"C:\Games\Steam\steamapps\common\Fallout 3 goty\Data"),
    "fnv": Path(r"C:\Games\Steam\steamapps\common\Fallout New Vegas\Data"),
}
MASTERS = {
    "fo3": ("fallout3", "anchorage", "thepitt", "brokensteel", "pointlookout", "zeta"),
    "fnv": ("falloutnv", "deadmoney", "honesthearts", "oldworldblues",
            "lonesomeroad", "gunrunnersarsenal", "caravanpack",
            "classicpack", "mercenarypack", "tribalpack"),
}
ESMS = {"fo3": "Fallout34.esm", "fnv": "FalloutNV34.esm"}
PLAN_FILES = {
    "fo3": (
        "indexed_patch_plan_candidates.jsonl.gz",
        "indexed_patch_plan_v2_strict_extra.jsonl.gz",
        "xtranslator_verified_visible_extra.jsonl.gz",
        "manual_visible_translation_verified.jsonl.gz",
        "sibling_info_field_verified.jsonl.gz",
        "import_manifest_migrated_verified.jsonl.gz",
        "cross_field_long_text_verified.jsonl.gz",
    ),
    "fnv": (
        "indexed_patch_plan_candidates.jsonl.gz",
        "indexed_patch_plan_v2_strict_extra.jsonl.gz",
        "xtranslator_verified_visible_extra.jsonl.gz",
        "manual_visible_translation_verified.jsonl.gz",
        "sibling_info_field_verified.jsonl.gz",
        "import_manifest_migrated_verified.jsonl.gz",
        "fnv_cross_field_long_text_verified.jsonl.gz",
    ),
}
# A strict migration table. The original file's *actual type/field* is required,
# not just a Korean dictionary occurrence with the same words.
MIGRATION = {
    ("INFO", "RNAM"): {("DIAL", "FULL"), ("INFO", "RNAM"), ("INFO", "NAM1")},
    ("INFO", "NAM1"): {("INFO", "NAM1"), ("INFO", "RNAM"), ("DIAL", "FULL")},
    ("TERM", "UNAM"): {("NOTE", "TNAM"), ("TERM", "RNAM"), ("TERM", "UNAM")},
    ("TERM", "ITXT"): {("TERM", "ITXT"), ("NOTE", "FULL"), ("TERM", "FULL")},
    ("TERM", "BTXT"): {("TERM", "BTXT"), ("TERM", "DESC"), ("TERM", "ITXT"),
                        ("NOTE", "FULL"), ("NOTE", "TNAM")},
    ("TERM", "FULL"): {("TERM", "FULL"), ("NOTE", "FULL"), ("TERM", "ITXT")},
    ("TERM", "RNAM"): {("TERM", "RNAM"), ("NOTE", "TNAM"), ("TERM", "ITXT")},
    ("MESG", "FULL"): {("MESG", "FULL")},
    ("MESG", "DESC"): {("MESG", "DESC")},
    ("MESG", "ITXT"): {("MESG", "ITXT")},
    ("QUST", "CNAM"): {("QUST", "CNAM")},
    ("BOOK", "DESC"): {("BOOK", "DESC")},
    ("BOOK", "FULL"): {("BOOK", "FULL")},
    ("NPC_", "FULL"): {("NPC_", "FULL"), ("CREA", "FULL")},
    ("MISC", "FULL"): {("MISC", "FULL")},
    ("WEAP", "FULL"): {("WEAP", "FULL")},
    ("ARMO", "FULL"): {("ARMO", "FULL")},
    ("KEYM", "FULL"): {("KEYM", "FULL")},
    ("AMMO", "FULL"): {("AMMO", "FULL")},
    ("ALCH", "FULL"): {("ALCH", "FULL")},
    ("CELL", "FULL"): {("CELL", "FULL")},
    ("WRLD", "FULL"): {("WRLD", "FULL")},
    ("PERK", "FULL"): {("PERK", "FULL")},
    ("PERK", "DESC"): {("PERK", "DESC")},
    ("CONT", "FULL"): {("CONT", "FULL")},
    ("ACTI", "FULL"): {("ACTI", "FULL")},
    ("FURN", "FULL"): {("FURN", "FULL")},
    ("DOOR", "FULL"): {("DOOR", "FULL")},
    ("TACT", "FULL"): {("TACT", "FULL")},
}
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def rows(path):
    with gzip.open(path, "rt", encoding="utf8") as src:
        for line in src:
            yield json.loads(line)


def out(path, entries):
    with gzip.open(path, "wt", encoding="utf8", compresslevel=6) as dst:
        for record in entries:
            dst.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def field_key(r):
    return r["target_formid"].upper(), r["record_type"], r["field"], int(r["target_field_occurrence_index"])


def run(game):
    native = module("native_complete_sst", "recover_fnv_xtranslator_origin_verified.py")
    reader = module("sst_complete", "read_xtranslator_sst.py")
    dst = ROOT / "data" / game
    installed = FO4_DATA / ESMS[game]
    expected = json.loads((dst / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if digest(installed) != expected:
        raise RuntimeError(f"{game}: converted game ESM changed")

    current_plan = {}
    for path in PLAN_FILES[game]:
        for r in rows(dst / path):
            key = field_key(r)
            val = r["english"], r["korean"]
            if key in current_plan and current_plan[key] != val:
                raise RuntimeError(f"Pre-existing conflicting translation: {key}")
            current_plan[key] = val
    residual = {}
    text_residuals = defaultdict(list)
    for r in rows(dst / "xtranslator_residual_candidates.jsonl.gz"):
        key = r["formid"].upper(), r["record_type"], r["field"], int(r["index"])
        if key in current_plan:
            continue
        if (r["record_type"], r["field"]) not in MIGRATION:
            continue
        if int(r["formid"], 16) >> 24 == 0 or not r["english"].strip():
            continue
        if r["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        if r["conditional_proc"] is not None:
            continue
        if key in residual:
            raise RuntimeError(f"Duplicate xTranslator candidate {key}")
        residual[key] = r
        text_residuals[r["english"]].append(key)

    # Full dictionary coverage, not just short-listed SST keys. Record all
    # different translations per English so one record cannot silently steal
    # another record's short/ambiguous line.
    all_korean = defaultdict(set)
    original_sst = defaultdict(set)
    source_ids = defaultdict(set)
    sst_hashes = {}
    permitted = {n + ".esm" for n in MASTERS[game]}
    for name in MASTERS[game]:
        path = SST / (name + "_en_ko.sst")
        parsed = reader.parse_sst(path)
        sst_hashes[path.name] = parsed["sha256"]
        masters = [n.casefold() for n in parsed["master_files"]]
        for entry in parsed["records"]:
            en = entry["source"]
            if en not in text_residuals:
                continue
            ko = entry["korean"]
            if not ko or ko == en:
                continue
            fid = int(entry["form_id"], 16)
            if (fid >> 24) >= len(masters):
                continue
            owner = masters[fid >> 24]
            if owner not in permitted:
                continue
            local = fid & 0xFFFFFF
            src_type, src_field = entry["record_name"], entry["field_name"]
            all_korean[en].add(ko)
            source_key = owner, local, src_type, src_field, en
            original_sst[source_key].add((ko, path.name, int(entry["index"])))
            source_ids[owner].add(local)

    # Independently verify that every cited SST record actually exists with
    # the same original English, record type and field position in ORIGINAL
    # native game ESMs. A dangling legacy SST record cannot become evidence.
    native_origin = defaultdict(set)
    source_sha = {}
    verified_original_sst_rows = 0
    index_issues = Counter()
    for plugin, wanted in source_ids.items():
        path = ORIGINAL[game] / plugin
        if not path.is_file():
            raise FileNotFoundError(path)
        owner_index = native.original_owner_index(path)
        for local, record_type, decoded in native.esm_records(path, wanted, owner_index=owner_index):
            for (src_field, idx), en in decoded.items():
                if en is None or en not in text_residuals:
                    continue
                source_key = plugin, local, record_type, src_field, en
                translations = original_sst.get(source_key, set())
                for korean, sst_name, sst_index in translations:
                    if sst_index != idx:
                        index_issues["sst_index_differs_from_esm"] += 1
                        continue
                    native_origin[(en, record_type, src_field)].add(
                        (korean, plugin, local, sst_name, sst_index)
                    )
                    verified_original_sst_rows += 1
        source_sha[plugin] = digest(path)

    verified = []
    review = []
    counts = Counter()
    fieldcounts = Counter()
    for key, r in residual.items():
        english = r["english"]
        targetpair = r["record_type"], r["field"]
        original_kos = all_korean.get(english, set())
        if not original_kos:
            state = "not_found_in_source_sst"
            proof = set()
        elif len(original_kos) > 1:
            state = "different_translations_for_same_english"
            proof = set()
        else:
            proof = {
                (*source,)
                for stype, sfield in MIGRATION[targetpair]
                for source in native_origin.get((english, stype, sfield), set())
                if source[0] in original_kos
            }
            if not proof:
                state = "no_verified_source_esm_matching_migration_family"
            else:
                korean = next(iter(original_kos))
                if not korean.strip() or "\ufffd" in korean:
                    state = "bad_korean_string"
                elif Counter(TOKEN.findall(english)) != Counter(TOKEN.findall(korean)):
                    state = "protected_placeholder_mismatch"
                else:
                    state = "unique_sst_korean_and_original_esm_source_verified"
        counts[state] += 1
        fieldcounts[(targetpair, state)] += 1
        if state == "unique_sst_korean_and_original_esm_source_verified":
            verified.append({
                "target_formid": key[0],
                "record_type": key[1],
                "field": key[2],
                "target_field_occurrence_index": key[3],
                "english": english,
                "korean": korean,
                "plan_source": "complete_source_sst_unique_korean_exact_english_migration",
                "previous_unlinked_class": r["status"],
                "source_evidence": [
                    {"source_record_type": s_type, "source_field": s_field,
                     "plugin": plug, "local_formid": f"{loc:06X}", "sst": sst_name,
                     "sst_index": src_idx}
                    for s_type, s_field in sorted(MIGRATION[targetpair])
                    for ko, plug, loc, sst_name, src_idx
                    in sorted(native_origin.get((english, s_type, s_field), set()))
                    if ko == korean
                ][:12],
                "source_evidence_count": len(proof),
                "verification_note": "Original native ESM and SST record proof; converted target speaker or quest relation not established by text-only match",
            })
        else:
            review.append({
                "formid": key[0], "record_type": key[1], "field": key[2],
                "index": key[3], "english": english,
                "xtranslator_state": r["status"],
                "reason": state,
                "sst_distinct_korean": len(original_kos),
                "possible_translations": sorted(original_kos)[:3],
            })

    # Re-read every assigned target field from the original converted ESM,
    # preventing a generated or stale xTranslator field from being used.
    by_id = defaultdict(list)
    for record in verified:
        by_id[int(record["target_formid"], 16)].append(record)
    verified_ids = set()
    seen_ids = set()
    for form, rtype, fields in native.esm_records(installed, set(by_id)):
        if form in seen_ids:
            raise RuntimeError(f"Duplicate FormID in converted ESM: {form:08X}")
        seen_ids.add(form)
        for r in by_id[form]:
            field = r["field"], r["target_field_occurrence_index"]
            if rtype != r["record_type"] or fields.get(field) != r["english"]:
                raise RuntimeError(f"Proposed target ESM field differs: {field} on {form:08X}")
            key = field_key(r)
            if key in verified_ids:
                raise RuntimeError(f"Proposed duplicate target field: {key}")
            verified_ids.add(key)
    if len(verified_ids) != len(verified):
        raise RuntimeError(f"{len(verified)-len(verified_ids)} missing translated target fields")
    if digest(installed) != expected:
        raise RuntimeError("Converted target ESM changed during scan")
    verified.sort(key=field_key)
    out(dst / "complete_sst_exact_migration_verified.jsonl.gz", verified)
    out(dst / "complete_sst_exact_migration_review.jsonl.gz", review)
    report = {
        "game": game,
        "converted_esm_sha256": expected,
        "source_esm_sha256": source_sha,
        "source_sst_sha256": sst_hashes,
        "previous_active_plan": len(current_plan),
        "eligible_remaining_fields": len(residual),
        "distinct_english_in_remaining": len(text_residuals),
        "verified_native_source_sst_occurrences": verified_original_sst_rows,
        "verified_new_fields": len(verified),
        "review_fields": len(review),
        "classification": dict(counts),
        "by_target_type_field": {
            f"{p[0]}/{p[1]}": {status: count for ((pp, status), count) in fieldcounts.items() if pp == p}
            for p, _ in fieldcounts
        },
        "original_sst_index_problems": dict(index_issues),
        "warning": "Source ESM + SST are verified. Target field bytes verified. Target speaker/quest/context not proven by text-only match; QA remains required. No game assets altered.",
    }
    (dst / "complete_sst_exact_migration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(game, "NEW", len(verified), "REVIEW", len(review),
          "CLASS", dict(counts), "TOP_FIELDS",
          Counter((r["record_type"], r["field"]) for r in verified).most_common(18),
          flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("game", choices=MASTERS)
    run(parser.parse_args().game)
