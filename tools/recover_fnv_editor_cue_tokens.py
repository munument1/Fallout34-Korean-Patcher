"""Repair original SST Korean dialogue whose converter-retained editor markers were omitted.

The existing complete-SST provenance verification already proved these
original ESM/SST source fields but deferred them because protected markers
such as {Cannibal}, {DUPE}, {Dog} or suffix {alive} are absent in the Korean.
Preserve these markers at the exact same outer edge and reject any field
whose other game tokens do not match. This is NOT a general regex translation
or removal of variables, and does not edit the installed plugin.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
import re
from pathlib import Path

import recover_complete_sst_exact_text as common

DATA = common.ROOT / "data" / "fnv"
ESM = common.FO4_DATA / "FalloutNV34.esm"
LEADING = re.compile(r"^((?:\{[A-Za-z][A-Za-z0-9_]*\}[ \t]*)+)")
TRAILING = re.compile(r"((?:[ \t]*\{[A-Za-z][A-Za-z0-9_]*\})+)$")


def repair(english: str, korean: str) -> str | None:
    prefix = LEADING.match(english)
    suffix = TRAILING.search(english)
    if not prefix and not suffix:
        return None
    left = prefix.group(1) if prefix else ""
    right = suffix.group(1) if suffix else ""
    if not left and not right:
        return None
    if left and korean.lstrip().startswith(left.strip()):
        left = ""
    if right and korean.rstrip().endswith(right.strip()):
        right = ""
    patched = left + korean + right
    return patched if Counter(common.TOKEN.findall(english)) == Counter(common.TOKEN.findall(patched)) else None


def run():
    native = common.module("native_editor_marker", "recover_fnv_xtranslator_origin_verified.py")
    reader = common.module("source_editor_marker", "read_xtranslator_sst.py")
    expected = json.loads((DATA / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(ESM) != expected:
        raise RuntimeError("FNV target changed")
    active = {}
    for filename in (*common.PLAN_FILES["fnv"],
                     "complete_sst_exact_migration_verified.jsonl.gz",
                     "skill_prefix_verified.jsonl.gz"):
        for row in common.rows(DATA / filename):
            k = common.field_key(row)
            value = row["english"], row["korean"]
            if k in active and active[k] != value:
                raise RuntimeError("Conflicting earlier plan")
            active[k] = value
    source_candidates = {}
    source_ids = defaultdict(set)
    original_sst = defaultdict(set)
    source_hashes = {}
    for row in common.rows(DATA / "complete_sst_exact_migration_review.jsonl.gz"):
        if row["reason"] != "protected_placeholder_mismatch" or len(row["possible_translations"]) != 1:
            continue
        key = row["formid"], row["record_type"], row["field"], int(row["index"])
        if key in active:
            continue
        en = row["english"]
        ko = repair(en, row["possible_translations"][0])
        if ko is None:
            continue
        source_candidates[key] = (en, ko, row["possible_translations"][0])
    wanted = {v[0] for v in source_candidates.values()}
    permitted = {name + ".esm" for name in common.MASTERS["fnv"]}
    for name in common.MASTERS["fnv"]:
        path = common.SST / (name + "_en_ko.sst")
        parsed = reader.parse_sst(path)
        source_hashes[path.name] = parsed["sha256"]
        masters = [x.casefold() for x in parsed["master_files"]]
        for entry in parsed["records"]:
            if entry["source"] not in wanted:
                continue
            fid = int(entry["form_id"], 16)
            if fid >> 24 >= len(masters):
                continue
            owner = masters[fid >> 24]
            if owner not in permitted:
                continue
            k = owner, fid & 0xFFFFFF, entry["record_name"], entry["field_name"], entry["source"]
            original_sst[k].add((entry["korean"], path.name, int(entry["index"])))
            source_ids[owner].add(fid & 0xFFFFFF)
    original_proof = defaultdict(list)
    original_hashes = {}
    for plugin, ids in source_ids.items():
        path = common.ORIGINAL["fnv"] / plugin
        owner = native.original_owner_index(path)
        for local, typ, fields in native.esm_records(path, ids, owner_index=owner):
            for (field, idx), en in fields.items():
                match = original_sst.get((plugin, local, typ, field, en), set())
                for ko, sstfile, sstidx in match:
                    if idx != sstidx or en not in wanted:
                        continue
                    original_proof[(typ, field, en, ko)].append(
                        (plugin, local, sstfile, sstidx)
                    )
        original_hashes[plugin] = common.digest(path)

    translated = []
    review = []
    status = Counter()
    for key, (en, fixed, original_ko) in source_candidates.items():
        candidates = []
        # The entire original ESM and native SST source text must be exactly
        # the same. Only the editor marker's position in the Korean changes.
        for typ, field in common.MIGRATION[(key[1], key[2])]:
            candidates.extend(original_proof.get((typ, field, en, original_ko), []))
        candidates = sorted(set(candidates))
        if not candidates:
            reason = "no_verified_matching_native_sst_entry"
        else:
            reason = "original_native_esm_and_editor_token_restored"
        status[reason] += 1
        if reason == "original_native_esm_and_editor_token_restored":
            translated.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "target_field_occurrence_index": key[3], "english": en,
                "korean": fixed,
                "plan_source": "fnv_original_sst_with_converter_editor_marker_preserved",
                "source_evidence": [
                    {"original_plugin": p, "original_formid": f"{fid:06X}",
                     "sst": sf, "sst_field_index": idx}
                    for p, fid, sf, idx in candidates[:8]
                ],
                "review_note": "Restored only braced editor-like tokens at English prefix/suffix",
            })
        else:
            review.append({
                "formid": key[0], "record_type": key[1], "field": key[2],
                "index": key[3], "english": en, "suggested_korean": fixed,
                "reason": reason,
            })
    # Target data byte verification.
    byid = defaultdict(list)
    for r in translated:
        byid[int(r["target_formid"], 16)].append(r)
    visited = set()
    found = set()
    for fid, typ, fields in native.esm_records(ESM, set(byid)):
        if fid in visited:
            raise RuntimeError("Duplicate converted target ID")
        visited.add(fid)
        for r in byid[fid]:
            k = common.field_key(r)
            if typ != r["record_type"] or fields.get((r["field"], r["target_field_occurrence_index"])) != r["english"]:
                raise RuntimeError("Wrong original converted target text")
            if k in found:
                raise RuntimeError("Duplicate targeted field")
            found.add(k)
    if len(found) != len(translated) or common.digest(ESM) != expected:
        raise RuntimeError("Unexpected target ESM content")
    translated.sort(key=common.field_key)
    common.out(DATA / "editor_marker_verified.jsonl.gz", translated)
    common.out(DATA / "editor_marker_review.jsonl.gz", review)
    report = {
        "game": "fnv", "converted_esm_sha256": expected,
        "source_sst_sha256": source_hashes, "source_esm_sha256": original_hashes,
        "possible_boundary_editor_marker_repairs": len(source_candidates),
        "verified_new_fields": len(translated), "still_review": len(review),
        "counts": dict(status),
        "warning": "Only original SST Korean plus an omitted editor-like marker, preserved at its original boundary. Runtime display/markup semantics and context still require QA. No ESM written.",
    }
    (DATA / "editor_marker_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print("FNV EDITOR_MARKERS", len(translated), "REVIEW", len(review),
          "STATUS", dict(status), flush=True)


if __name__ == "__main__":
    run()
