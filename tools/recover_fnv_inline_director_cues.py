"""Restore FNV COMPLETE SST lines altered when Fallout34 removes {director cues}.

Examples of loss:
  native INFO/NAM1: {delighted}If ... mighty {KAI-zar}Caesar!
  converted INFO/NAM1: If ... mighty Caesar!
  native Korean SST: 위대하신 카이사르의 뜻을 ...

Only removable braced, NON-NESTED original editorial annotations are handled.
Every candidate requires:
  - the exact original SST source English + Korean, with owner/master and index;
  - actual original FalloutNV+DLC ESM record with same FormID/type/field/index;
  - an exact *deterministic* cue-removal transformation to converted English;
  - just one Korean after applying the same cue removal to its translation;
  - exact converted target FormID/type/field/index/English and placeholders.
No fuzzy similarity, model translation, native assets or online mod modification.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re

import recover_complete_sst_exact_text as common

DATA = common.ROOT / "data" / "fnv"
TARGET = common.FO4_DATA / "FalloutNV34.esm"
ANNOTATION = re.compile(r"\{[^{}\r\n]{1,180}\}")
FOLLOWING_WS = re.compile(r"\{[^{}\r\n]{1,180}\}[ \t]*")
PRECEDING_WS = re.compile(r"[ \t]*\{[^{}\r\n]{1,180}\}")
FIELDS = {("INFO", "NAM1"), ("INFO", "RNAM")}
NATIVE = {("INFO", "NAM1"), ("INFO", "RNAM"), ("DIAL", "FULL")}


def converted_english_options(src: str) -> set[tuple[str, str]]:
    """Only literal cue-removal alternatives observed in Fallout34 text.

    Never normalize punctuation or rewrite ordinary words; this is required to
    avoid false positives when several English responses share a similar idea.
    """
    if "{" not in src or not ANNOTATION.search(src):
        return set()
    candidates = {
        ("braces_only", ANNOTATION.sub("", src)),
        ("braces_and_following_whitespace", FOLLOWING_WS.sub("", src)),
        ("preceding_whitespace_and_braces", PRECEDING_WS.sub("", src)),
    }
    # Converter also collapses extra spaces left by inline cue removals.
    candidates |= {
        (mode + "_space_collapse", re.sub(r"[ \t]{2,}", " ", value))
        for mode, value in tuple(candidates)
    }
    return {
        (name, value) for name, value in candidates
        if value and value != src
    }


def cleaned_korean(text: str) -> str:
    # The same converter removes non-gameplay direction annotations from the
    # subtitle. Real numeric and game-format variables remain protected below.
    return ANNOTATION.sub("", text)


def run():
    native = common.module("native_inline_fnv", "recover_fnv_xtranslator_origin_verified.py")
    reader = common.module("sst_inline_fnv", "read_xtranslator_sst.py")
    expected = json.loads((DATA / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(TARGET) != expected:
        raise RuntimeError("FNV target ESM SHA256 changed")
    active = {}
    for name in (*common.PLAN_FILES["fnv"],
                 "complete_sst_exact_migration_verified.jsonl.gz",
                 "skill_prefix_verified.jsonl.gz", "editor_marker_verified.jsonl.gz"):
        for row in common.rows(DATA / name):
            key = common.field_key(row)
            val = row["english"], row["korean"]
            if key in active and active[key] != val:
                raise RuntimeError(f"Pre-existing conflicting translation {key}")
            active[key] = val

    residual = {}
    wanted = set()
    for r in common.rows(DATA / "xtranslator_residual_candidates.jsonl.gz"):
        key = r["formid"], r["record_type"], r["field"], int(r["index"])
        if key in active or (r["record_type"], r["field"]) not in FIELDS:
            continue
        if r["conditional_proc"] is not None or int(r["formid"], 16) >> 24 == 0:
            continue
        if not r["english"].strip():
            continue
        residual[key] = r
        wanted.add(r["english"])

    target_to_source = defaultdict(set)
    by_source_id = defaultdict(set)
    owner_indices = defaultdict(set)
    sst_sha = {}
    source_plugins = {name + ".esm" for name in common.MASTERS["fnv"]}
    # Native SST captures original speech-direction braces that target removed.
    for name in common.MASTERS["fnv"]:
        source_path = common.SST / (name + "_en_ko.sst")
        parsed = reader.parse_sst(source_path)
        sst_sha[source_path.name] = parsed["sha256"]
        masters = [p.casefold() for p in parsed["master_files"]]
        for row in parsed["records"]:
            src = row["source"]
            if not src or not row["korean"] or (row["record_name"], row["field_name"]) not in NATIVE:
                continue
            options = [(mode, transformed) for mode, transformed
                       in converted_english_options(src) if transformed in wanted]
            if not options:
                continue
            fid = int(row["form_id"], 16)
            if fid >> 24 >= len(masters):
                continue
            plugin = masters[fid >> 24]
            if plugin not in source_plugins:
                continue
            korean = cleaned_korean(row["korean"])
            if not korean.strip():
                continue
            for mode, english in options:
                target_to_source[english].add(
                    (korean, plugin, fid & 0xFFFFFF, row["record_name"],
                     row["field_name"], int(row["index"]), src, source_path.name, mode)
                )
            by_source_id[plugin].add(fid & 0xFFFFFF)

    # Validate source original bytes and SST entry indices. A source SST record
    # may be stale, so never use it merely because the candidate text matches.
    source_match = defaultdict(set)
    native_hashes = {}
    by_original = defaultdict(set)
    for transformed, orig_entries in target_to_source.items():
        for entry in orig_entries:
            ko, plugin, local, rectype, field, idx, original_en, file, mode = entry
            by_original[(plugin, local, rectype, field, idx, original_en)].add((transformed, entry))
    for plugin, ids in by_source_id.items():
        source_path = common.ORIGINAL["fnv"] / plugin
        owner = native.original_owner_index(source_path)
        for local, rectype, decoded in native.esm_records(source_path, ids, owner_index=owner):
            for (field, idx), english in decoded.items():
                for transformed, entry in by_original.get(
                    (plugin, local, rectype, field, idx, english), set()
                ):
                    source_match[transformed].add(entry)
        native_hashes[plugin] = common.digest(source_path)

    accepted, deferred = [], []
    reasons = Counter()
    byfield = defaultdict(Counter)
    for key, row in residual.items():
        english = row["english"]
        hits = source_match.get(english, set())
        if not hits:
            # Do not enumerate all remaining fields as deferred: original
            # strings without any removable cue are out of this script's scope.
            continue
        matches = defaultdict(set)
        for entry in hits:
            korean, plugin, local, typ, field, index, original_en, sstname, mode = entry
            if (typ, field) not in common.MIGRATION[(key[1], key[2])]:
                continue
            if korean == english or not korean.strip():
                continue
            if "\ufffd" in korean:
                continue
            if Counter(common.TOKEN.findall(english)) != Counter(common.TOKEN.findall(korean)):
                continue
            matches[korean].add((plugin, local, typ, field, index, original_en, sstname, mode))
        if len(matches) == 1:
            korean, proofs = next(iter(matches.items()))
            state = "native_source_sst_editor_cue_elision_proven"
            accepted.append({
                "target_formid": key[0], "record_type": key[1], "field": key[2],
                "target_field_occurrence_index": key[3], "english": english,
                "korean": korean,
                "plan_source": "fnv_inline_speech_direction_cue_removed_original_sst",
                "previous_unlinked_state": row["status"],
                "source_evidence": [
                    {"plugin": plugin, "original_formid": f"{form:06X}", "record_type": tp,
                     "field": field, "index": idx, "original_english": original_text,
                     "sst": sst, "conversion": transform}
                    for plugin, form, tp, field, idx, original_text, sst, transform in sorted(proofs)
                ][:6],
                "source_match_count": len(proofs),
                "warning": "Original ESM/SST field and deterministic cue removal verified; converter FormID identity not established, in-game context QA required",
            })
        elif not matches:
            state = "original_source_proven_but_no_valid_formatted_korean"
        else:
            state = "different_korean_after_same_cue_removal"
        reasons[state] += 1
        byfield[key[1] + "/" + key[2]][state] += 1
        if state != "native_source_sst_editor_cue_elision_proven":
            deferred.append({
                "formid": key[0], "record_type": key[1], "field": key[2],
                "index": key[3], "english": english, "reason": state,
                "possible_korean": sorted(matches.keys())[:4],
                "source_candidates_count": len(hits),
            })

    # Independent target ESM validation.
    by_fid = defaultdict(list)
    for row in accepted:
        by_fid[int(row["target_formid"], 16)].append(row)
    visited = set()
    found = set()
    for fid, rectype, decoded in native.esm_records(TARGET, set(by_fid)):
        if fid in visited:
            raise RuntimeError(f"Duplicate target FormID {fid:08X}")
        visited.add(fid)
        for row in by_fid[fid]:
            k = common.field_key(row)
            if rectype != row["record_type"] or decoded.get((row["field"], row["target_field_occurrence_index"])) != row["english"]:
                raise RuntimeError(f"Changed target ESM field {k}")
            if k in found:
                raise RuntimeError(f"Duplicate target field {k}")
            found.add(k)
    if len(found) != len(accepted) or common.digest(TARGET) != expected:
        raise RuntimeError("Incomplete target verification or target ESM changed")

    accepted.sort(key=common.field_key)
    common.out(DATA / "inline_director_cues_verified.jsonl.gz", accepted)
    common.out(DATA / "inline_director_cues_review.jsonl.gz", deferred)
    report = {
        "game": "fnv",
        "converted_esm_sha256": expected,
        "original_esm_sha256": native_hashes,
        "original_korean_sst_sha256": sst_sha,
        "eligible_unlinked_dialogue_field_occurrences": len(residual),
        "distinct_target_english": len(wanted),
        "source_sst_with_removable_cues": len(target_to_source),
        "native_esm_source_verification_hits": len(source_match),
        "newly_verified_fields": len(accepted),
        "requires_context_review": len(deferred),
        "classification": dict(reasons),
        "by_target_field": {k: dict(v) for k, v in byfield.items()},
        "warning": "Only deterministic removal of literal original {editor/speech direction cues} and whitespace directly adjacent to them. Source ESM/SST and target ESM fields independently proven. Does not establish generated target speaker identity or actual runtime render. No ESM/ESP/BA2 files generated or edited.",
    }
    (DATA / "inline_director_cues_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print("FNV INLINE CUES", len(accepted), "REVIEW", len(deferred),
          "REASONS", dict(reasons), "TARGET", dict(Counter(
              row["record_type"] + "/" + row["field"] for row in accepted)), flush=True)


if __name__ == "__main__":
    run()
