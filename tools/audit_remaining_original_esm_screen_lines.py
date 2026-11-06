"""Classify Fallout34 residual visible English against native original game ESMs.

Purpose: distinguish a genuinely unmatched *original in-game sentence* from
FO4 converter-generated editor/terminal/UI data or a dialogue string mutated
during conversion. This scans both original ESMs and converted text plans but
NEVER edits or copies game assets. A source text hit is NOT sufficient proof
for adding a translation plan; this script only audits.
"""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

import recover_complete_sst_exact_text as common

ROOT = common.ROOT
NATIVE_FIELDS = {
    ("DIAL", "FULL"), ("INFO", "RNAM"), ("INFO", "NAM1"),
    ("TERM", "UNAM"), ("TERM", "RNAM"), ("TERM", "ITXT"),
    ("TERM", "DESC"), ("TERM", "FULL"), ("NOTE", "TNAM"),
    ("NOTE", "FULL"), ("MESG", "DESC"), ("MESG", "ITXT"), ("MESG", "FULL"),
    ("QUST", "CNAM"), ("BOOK", "DESC"), ("BOOK", "FULL"),
    ("NPC_", "FULL"), ("CREA", "FULL"), ("MISC", "FULL"),
    ("ARMO", "FULL"), ("WEAP", "FULL"), ("PERK", "DESC"),
    ("PERK", "FULL"), ("CELL", "FULL"), ("ALCH", "FULL"),
    ("ACTI", "FULL"), ("KEYM", "FULL"), ("CONT", "FULL"),
}


def main():
    fnv = common.module("audit_remaining_original_esm", "recover_fnv_xtranslator_origin_verified.py")
    fo3 = common.module("audit_remaining_fo3", "recover_fo3_xtranslator_provenance.py")
    for game in ("fo3", "fnv"):
        data = ROOT / "data" / game
        planned = set()
        files = [*common.PLAN_FILES[game], "complete_sst_exact_migration_verified.jsonl.gz",
                 "skill_prefix_verified.jsonl.gz"]
        if game == "fo3":
            files.append("ttw_foreign_master_text_verified.jsonl.gz")
        else:
            files.append("editor_marker_verified.jsonl.gz")
            files.append("inline_director_cues_verified.jsonl.gz")
        for name in files:
            for r in common.rows(data / name):
                planned.add(common.field_key(r))
        unlinked = defaultdict(list)
        for r in common.rows(data / "xtranslator_residual_candidates.jsonl.gz"):
            k = r["formid"], r["record_type"], r["field"], int(r["index"])
            if k in planned:
                continue
            if (r["record_type"], r["field"]) not in common.MIGRATION:
                continue
            if r["conditional_proc"] is not None or int(r["formid"], 16) >> 24 == 0:
                continue
            if not r["english"].strip():
                continue
            unlinked[r["english"]].append(r)
        source = defaultdict(set)
        source_hashes = {}
        for part in common.MASTERS[game]:
            path = common.ORIGINAL[game] / (part + ".esm")
            owner = fnv.original_owner_index(path)
            for f, at, size, flags, fid, tp in fo3.records(path):
                if fid >> 24 != owner:
                    continue
                if tp not in {x[0] for x in NATIVE_FIELDS}:
                    continue
                for tag, idx, raw in fo3.fields(fo3.read_record(f, at, size, flags)):
                    if (tp, tag) not in NATIVE_FIELDS:
                        continue
                    text = fo3.decode(raw)
                    if text in unlinked:
                        source[text].add((tp, tag, part + ".esm", fid & 0xFFFFFF))
            source_hashes[part + ".esm"] = common.digest(path)
        classification = Counter()
        detail = defaultdict(Counter)
        examples = defaultdict(list)
        for english, rows in unlinked.items():
            originals = source.get(english, set())
            for r in rows:
                target_field = r["record_type"], r["field"]
                compatible = [
                    (tp, fld, p, fid) for tp, fld, p, fid in originals
                    if (tp, fld) in common.MIGRATION[target_field]
                ]
                exact = [
                    a for a in originals
                    if (a[0], a[1]) == target_field
                ]
                if not originals:
                    state = "no_exact_english_in_original_native_esm"
                elif exact:
                    state = "original_exact_type_field_found_no_korean_link"
                elif compatible:
                    state = "original_field_migration_found_no_korean_link"
                else:
                    state = "original_english_only_other_unrelated_fields"
                classification[state] += 1
                detail[r["record_type"] + "/" + r["field"]][state] += 1
                if len(examples[state]) < 10:
                    examples[state].append({
                        "target": r["formid"], "field": "/".join(target_field),
                        "english": english[:180],
                        "native_original": [
                            f"{p}:{fid:06X}:{tp}/{fld}" for tp, fld, p, fid in sorted(originals)[:4]
                        ],
                    })
        result = {
            "game": game, "examined_fields": sum(map(len, unlinked.values())),
            "unique_english": len(unlinked),
            "source_original_esm_sha256": source_hashes,
            "classification": dict(classification),
            "by_target_type_field": {k: dict(v) for k, v in sorted(detail.items())},
            "examples": dict(examples),
            "warning": "Static original game ESM comparison. The target may be converter-authored/rewritten, or source SST may not cover this field. No assumption about runtime display. No patch created.",
        }
        (data / "original_native_remaining_screen_audit.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
        print(game, "ROWS", result["examined_fields"], "CLASS", dict(classification),
              "INFO_NAM1", dict(detail.get("INFO/NAM1", {})),
              "TERM_UNAM", dict(detail.get("TERM/UNAM", {})), flush=True)


if __name__ == "__main__":
    main()
