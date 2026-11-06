"""Recover FNV dialogue shifted only by converter punctuation/spacing changes.

The source is ORIGINAL native ESM + matching SST at the SAME original
plugin/record/field/index. Converted lines must normalize identically with a
small deterministic punctuation map, not fuzzy similarity. Distinct original
Korean values for a normalized line are rejected. No game files are written.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

import recover_complete_sst_exact_text as common
from translation_work_filter import classify

DATA = common.ROOT / "data" / "fnv"
TARGET = common.FO4_DATA / "FalloutNV34.esm"
FIELDS = {("INFO", "NAM1"), ("INFO", "RNAM")}
ACTIVE_EXTRAS = (
    "complete_sst_exact_migration_verified.jsonl.gz",
    "skill_prefix_verified.jsonl.gz", "editor_marker_verified.jsonl.gz",
    "inline_director_cues_verified.jsonl.gz",
)
PUNCT = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u02bc": "'",
    "\u201c": '"', "\u201d": '"',
    "\u00a0": " ",
})
SPACE = re.compile(r"[ \t]{2,}")


def normalize(value: str) -> str:
    # Intentionally do NOT normalize words, brackets, braces or skill checks.
    return SPACE.sub(" ", value.translate(PUNCT)).replace("\r\n", "\n").strip()


def eligible(text: str) -> bool:
    return len(text) >= 24 and len(text.split()) >= 4


def recover() -> None:
    native = common.module("punct_native", "recover_fnv_xtranslator_origin_verified.py")
    reader = common.module("punct_reader", "read_xtranslator_sst.py")
    expected = json.loads((DATA / "indexed_plan_report.json").read_text("utf-8"))["esm_sha256"]
    if common.digest(TARGET) != expected:
        raise RuntimeError("FNV converted ESM changed since plan was created")
    planned = {}
    for file in (*common.PLAN_FILES["fnv"], *ACTIVE_EXTRAS):
        for row in common.rows(DATA / file):
            key = common.field_key(row)
            value = row["english"], row["korean"]
            if key in planned and planned[key] != value:
                raise RuntimeError(f"Conflicting existing plan for {key}")
            planned[key] = value

    residual = {}
    by_norm = defaultdict(set)
    for row in common.rows(DATA / "xtranslator_residual_candidates.jsonl.gz"):
        key = row["formid"].upper(), row["record_type"], row["field"], int(row["index"])
        if key in planned or (row["record_type"], row["field"]) not in FIELDS:
            continue
        if row["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        if classify(row)[0] != "actionable" or not eligible(row["english"]):
            continue
        residual[key] = row
        by_norm[normalize(row["english"])].add(row["english"])

    # Find original dictionary lines with small, EXACTLY specified converter
    # differences. No raw text match is accepted by this stage.
    dict_by_origin = defaultdict(set)
    candidate_ids = defaultdict(set)
    for master in common.MASTERS["fnv"]:
        path = common.SST / (master + "_en_ko.sst")
        parsed = reader.parse_sst(path)
        masters = [x.casefold() for x in parsed["master_files"]]
        for row in parsed["records"]:
            eng = row["source"]
            if not eligible(eng) or (row["record_name"], row["field_name"]) not in {
                ("INFO", "RNAM"), ("INFO", "NAM1"), ("DIAL", "FULL")
            }:
                continue
            norm = normalize(eng)
            targets = by_norm.get(norm)
            if not targets or eng in targets or not row["korean"] or row["korean"] == eng:
                continue
            fid = int(row["form_id"], 16)
            if fid >> 24 >= len(masters):
                continue
            owner = masters[fid >> 24]
            if owner not in {p + ".esm" for p in common.MASTERS["fnv"]}:
                continue
            key = (owner, fid & 0xFFFFFF, row["record_name"],
                   row["field_name"], int(row["index"]), eng)
            dict_by_origin[key].add((row["korean"], path.name))
            candidate_ids[owner].add(fid & 0xFFFFFF)

    verified_sources = defaultdict(set)
    source_hashes = {}
    for owner, ids in candidate_ids.items():
        source = common.ORIGINAL["fnv"] / owner
        own_index = native.original_owner_index(source)
        for local, typ, fields in native.esm_records(source, ids, owner_index=own_index):
            for (field, index), original in fields.items():
                key = (owner, local, typ, field, index, original)
                for korean, sst in dict_by_origin.get(key, ()):
                    normalized = normalize(original)
                    if normalized not in by_norm:
                        continue
                    verified_sources[normalized].add((
                        korean, owner, local, typ, field, index, original, sst
                    ))
        source_hashes[owner] = common.digest(source)

    accepted, review = [], []
    statuses = Counter()
    for key, row in residual.items():
        english = row["english"]
        hits = verified_sources.get(normalize(english), set())
        valid = defaultdict(set)
        for ko, owner, local, src_type, src_field, index, original, sst in hits:
            if english == original or (src_type, src_field) not in common.MIGRATION[(key[1], key[2])]:
                continue
            if not ko.strip() or "\ufffd" in ko:
                continue
            if Counter(common.TOKEN.findall(english)) != Counter(common.TOKEN.findall(ko)):
                continue
            valid[ko].add((owner, local, src_type, src_field, index, original, sst))
        if not valid:
            continue
        if len(valid) != 1:
            statuses["conflicting_original_korean"] += 1
            review.append({"formid": key[0], "record_type": key[1],
                           "field": key[2], "index": key[3], "english": english,
                           "reason": "conflicting_original_korean",
                           "candidate_count": len(valid)})
            continue
        ko, evidence = next(iter(valid.items()))
        statuses["source_verified_punctuation_normalization"] += 1
        accepted.append({
            "target_formid": key[0], "record_type": key[1], "field": key[2],
            "target_field_occurrence_index": key[3],
            "english": english, "korean": ko,
            "plan_source": "fnv_verified_original_punctuation_normalization",
            "source_evidence": [
                {"original_plugin": owner, "local_formid": f"{local:06X}",
                 "record_type": tp, "field": field, "index": i,
                 "original_english": source_en, "sst": sst}
                for owner, local, tp, field, i, source_en, sst in sorted(evidence)[:8]
            ],
            "context_warning": "Exact deterministic punctuation/spacing equivalence only; target speaker not guaranteed by FormID mapping",
        })

    # Read back the proposed target positions from the installed ESM.
    byid = defaultdict(list)
    for row in accepted:
        byid[int(row["target_formid"], 16)].append(row)
    found = set()
    seen = set()
    for fid, typ, fields in native.esm_records(TARGET, set(byid)):
        if fid in seen:
            raise RuntimeError(f"Duplicate target FormID {fid:08X}")
        seen.add(fid)
        for row in byid[fid]:
            key = common.field_key(row)
            if typ != row["record_type"] or fields.get(
                    (row["field"], row["target_field_occurrence_index"])) != row["english"]:
                raise RuntimeError(f"Converted ESM source text mismatch at {key}")
            if key in found:
                raise RuntimeError(f"Duplicate target field {key}")
            found.add(key)
    if len(found) != len(accepted) or common.digest(TARGET) != expected:
        raise RuntimeError("FNV punctuation repair target validation failed")

    accepted.sort(key=common.field_key)
    common.out(DATA / "punctuation_normalized_verified.jsonl.gz", accepted)
    common.out(DATA / "punctuation_normalized_review.jsonl.gz", review)
    report = {
        "game": "fnv", "target_sha256": expected,
        "original_source_sha256": source_hashes,
        "candidate_target_dialogue_fields": len(residual),
        "verified_new_fields": len(accepted), "needs_context_review": len(review),
        "status": dict(statuses),
        "warning": "Only original ESM + SST verified, then deterministic punctuation mapping. No ESM written.",
    }
    (DATA / "punctuation_normalized_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("FNV_PUNCT_RECOVERY", json.dumps({
        "eligible": len(residual), "accepted": len(accepted), "review": len(review),
        "status": dict(statuses),
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    recover()
