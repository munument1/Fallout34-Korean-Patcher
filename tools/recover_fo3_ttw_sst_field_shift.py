"""Recover Fallout 3 dialogue lost because FO3 SST contains TTW FNV masters.

Fallout3_en_ko.sst and FO3 DLC SSTs here are TTW-style: MAST[0..5] refer
to FalloutNV and its DLCs, not FO3. Previous FO3-origin-only matching ignored
those strings. These rows can still carry an exact translation for a FO3
original game field, but their FNV FormID must NOT be treated as a FO3 ID.

Eligible candidate requires:
 - TTW/FNV-owned translated row in a named FO3 source SST;
 - same English has exactly one Korean across that entire FO3 SST source family;
 - at least one *actual FO3 original native ESM* owns the exact English in a
   source field compatible with the converted target field;
 - all placeholders match; converted target bytes match the initial scan;
 - no existing plan assignment; no Fallout4 master field.

These are exact-text native-source/TTW-dictionary translation matches, not
proof of the original TTW FNV FormID corresponding to a FO3 FormID. Store
proof and flag them as requiring runtime contextual review. Game and online
mod files stay untouched.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

import recover_complete_sst_exact_text as common

DATA = common.ROOT / "data" / "fo3"
TARGET = common.FO4_DATA / "Fallout34.esm"
TTW_OWNERS = {
    "falloutnv.esm", "deadmoney.esm", "honesthearts.esm",
    "oldworldblues.esm", "lonesomeroad.esm", "gunrunnersarsenal.esm",
}
FO3_OWNERS = {name + ".esm" for name in common.MASTERS["fo3"]}


def run():
    native = common.module("ttw_sst_native", "recover_fnv_xtranslator_origin_verified.py")
    fo3 = common.module("ttw_esm", "recover_fo3_xtranslator_provenance.py")
    reader = common.module("ttw_sst_reader", "read_xtranslator_sst.py")
    expected = json.loads((DATA / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(TARGET) != expected:
        raise RuntimeError("FO3 converter ESM hash is different")
    active = {}
    for filename in (*common.PLAN_FILES["fo3"], "complete_sst_exact_migration_verified.jsonl.gz"):
        for r in common.rows(DATA / filename):
            k = common.field_key(r)
            v = r["english"], r["korean"]
            if k in active and active[k] != v:
                raise RuntimeError(f"Conflicting current plan {k}")
            active[k] = v
    residual = {}
    remaining_en = set()
    for r in common.rows(DATA / "xtranslator_residual_candidates.jsonl.gz"):
        k = r["formid"].upper(), r["record_type"], r["field"], int(r["index"])
        if (k in active or (r["record_type"], r["field"]) not in common.MIGRATION
                or int(k[0], 16) >> 24 == 0 or not r["english"].strip()
                or r["conditional_proc"] is not None):
            continue
        if r["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        residual[k] = r
        remaining_en.add(r["english"])
    all_kos = defaultdict(set)
    foreign = defaultdict(set)
    sst_hashes = {}
    for file in common.MASTERS["fo3"]:
        path = common.SST / (file + "_en_ko.sst")
        source = reader.parse_sst(path)
        sst_hashes[path.name] = source["sha256"]
        masters = [x.casefold() for x in source["master_files"]]
        for row in source["records"]:
            english = row["source"]
            if english not in remaining_en or not row["korean"] or row["korean"] == english:
                continue
            form = int(row["form_id"], 16)
            if form >> 24 >= len(masters):
                continue
            owner = masters[form >> 24]
            if owner not in TTW_OWNERS and owner not in FO3_OWNERS:
                continue
            all_kos[english].add(row["korean"])
            if owner in TTW_OWNERS:
                foreign[english].add((
                    row["korean"], path.name, owner, form & 0xFFFFFF,
                    row["record_name"], row["field_name"], int(row["index"])
                ))

    # Search ONLY FO3 + DLC original ESMs, never the FNV record that happens
    # to be referenced by a TTW load index.
    original = defaultdict(set)
    orig_hashes = {}
    wanted = set(foreign)
    for part in common.MASTERS["fo3"]:
        path = common.ORIGINAL["fo3"] / (part + ".esm")
        index = native.original_owner_index(path)
        for f, at, size, flags, fid, typ in fo3.records(path):
            if (fid >> 24) != index:
                continue
            for field, subidx, raw in fo3.fields(fo3.read_record(f, at, size, flags)):
                english = fo3.decode(raw)
                if english in wanted:
                    original[(english, typ, field)].add((part + ".esm", fid & 0xFFFFFF, subidx))
        orig_hashes[part + ".esm"] = common.digest(path)

    verified = []
    review = []
    status = Counter()
    byfield = Counter()
    for targetkey, row in residual.items():
        english = row["english"]
        entries = foreign.get(english, set())
        if not entries:
            continue
        translations = all_kos.get(english, set())
        family = common.MIGRATION[(targetkey[1], targetkey[2])]
        source_pairs = {(tp, fld) for _, _, _, _, tp, fld, _ in entries}
        matched_source = {
            (tp, fld): original.get((english, tp, fld), set())
            for tp, fld in family & source_pairs
            if original.get((english, tp, fld))
        }
        if len(translations) != 1:
            reason = "source_sst_has_conflicting_korean"
        elif not matched_source:
            reason = "no_fo3_native_esm_original_field_or_migration_match"
        else:
            ko = next(iter(translations))
            if "\ufffd" in ko or not ko.strip():
                reason = "bad_korean"
            elif Counter(common.TOKEN.findall(english)) != Counter(common.TOKEN.findall(ko)):
                reason = "protected_token_mismatch"
            else:
                reason = "original_fo3_esm_and_ttw_sst_exact_english_verified"
        status[reason] += 1
        byfield[(targetkey[1], targetkey[2], reason)] += 1
        if reason == "original_fo3_esm_and_ttw_sst_exact_english_verified":
            native_proof = [
                {"original_plugin": p, "original_formid": f"{fid:06X}",
                 "original_type": tp, "original_field": fld, "original_index": idx}
                for (tp, fld), refs in sorted(matched_source.items())
                for p, fid, idx in sorted(refs)
            ]
            ttw_proof = [
                {"sst_filename": sstname, "ttw_master_owner": owner, "ttw_formid": f"{local:06X}",
                 "sst_record_type": tp, "sst_field": field, "sst_index": idx}
                for translated, sstname, owner, local, tp, field, idx in sorted(entries)
                if translated == ko and (tp, field) in matched_source
            ]
            verified.append({
                "target_formid": targetkey[0], "record_type": targetkey[1],
                "field": targetkey[2], "target_field_occurrence_index": targetkey[3],
                "english": english, "korean": ko,
                "plan_source": "fo3_ttw_foreign_master_sst_with_original_fo3_esm_text",
                "previous_unlinked_class": row["status"],
                "source_evidence": {
                    "native_fo3_source_examples": native_proof[:6],
                    "native_fo3_source_match_count": len(native_proof),
                    "ttw_source_sst_examples": ttw_proof[:6],
                    "ttw_source_sst_match_count": len(ttw_proof),
                    "note": "TTW FNV master ID is not a FO3 ID; only text+source field independently proven",
                },
            })
        else:
            review.append({
                "target_formid": targetkey[0], "record_type": targetkey[1],
                "field": targetkey[2], "index": targetkey[3],
                "english": english, "reason": reason,
                "source_sst_distinct_korean": len(translations),
                "native_matching_field_count": sum(map(len, matched_source.values()))
            })

    # Re-read the target from the installed converted ESM.
    byid = defaultdict(list)
    for record in verified:
        byid[int(record["target_formid"], 16)].append(record)
    visited = set()
    matched_fields = set()
    for fid, typ, fields in native.esm_records(TARGET, set(byid)):
        if fid in visited:
            raise RuntimeError("Duplicate target FormID")
        visited.add(fid)
        for r in byid[fid]:
            key = common.field_key(r)
            if typ != r["record_type"] or fields.get((r["field"], r["target_field_occurrence_index"])) != r["english"]:
                raise RuntimeError(f"Converted target text mismatch: {key}")
            if key in matched_fields:
                raise RuntimeError(f"Duplicate patch target {key}")
            matched_fields.add(key)
    if len(matched_fields) != len(verified) or common.digest(TARGET) != expected:
        raise RuntimeError("Target validation incomplete or modified")
    verified.sort(key=common.field_key)
    common.out(DATA / "ttw_foreign_master_text_verified.jsonl.gz", verified)
    common.out(DATA / "ttw_foreign_master_text_review.jsonl.gz", review)
    report = {
        "game": "fo3",
        "converted_esm_sha256": expected,
        "source_fo3_esm_sha256": orig_hashes,
        "fo3_ttw_sst_sha256": sst_hashes,
        "eligible_remaining_field_occurrences": len(residual),
        "foreign_owner_sst_distinct_text": len(foreign),
        "new_fo3_foreign_owner_sst_reuse_candidates": len(verified),
        "needs_review": len(review),
        "classification": dict(status),
        "by_target_type_field": {
            f"{tp}/{fld}": {st: n for (a, b, st), n in byfield.items() if a == tp and b == fld}
            for tp, fld, _ in byfield
        },
        "warning": "This evidence is translation memory re-use, not a TTW->FO3 FormID crosswalk. Original FO3+SST target text verified, but gameplay context and runtime display still need QA. No game assets modified.",
    }
    (DATA / "ttw_foreign_master_text_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print("FO3 TTW FOREIGN", len(verified), "REVIEW", len(review),
          "STATUS", dict(status), "FIELD",
          Counter((r["record_type"], r["field"]) for r in verified).most_common(18), flush=True)


if __name__ == "__main__":
    run()
