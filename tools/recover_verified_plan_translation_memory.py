"""Reuse *already verified* Korean translations of exactly identical text.

Fallout34 copies or reconstructs on-screen labels into a different FO4 record
family. Such display strings may be absent from the SST at their NEW target
type/field yet an identical source already has an ESM-verified Korean string
in the current plan.

Safeguards: identical whole English, exactly one Korean across all verified
plans, specific role-compatible source/target field types, token invariants,
SHA-pinned target ESM and exact FormID/type/field/index. Never uses a fuzzy
translation or edits installed ESM/ESP. Runtime context still needs QA.
"""
from collections import Counter, defaultdict
import argparse
import json

import recover_complete_sst_exact_text as common
from recover_original_quest_objectives import FILE as QUEST_FILE
from translation_work_filter import classify

FILE = "verified_plan_translation_memory_verified.jsonl.gz"

# Semantic whitelist: reuse an ENTIRE, identical translated display string,
# without claiming ownership of a converter FormID or guessing a speaker.
_FULL = {
    ("ACTI", "FULL"), ("ALCH", "FULL"), ("AMMO", "FULL"),
    ("ARMO", "FULL"), ("BOOK", "FULL"), ("CELL", "FULL"),
    ("CONT", "FULL"), ("DOOR", "FULL"), ("FURN", "FULL"),
    ("KEYM", "FULL"), ("MISC", "FULL"), ("NOTE", "FULL"),
    ("NPC_", "FULL"), ("PERK", "FULL"), ("TACT", "FULL"),
    ("TERM", "FULL"), ("WEAP", "FULL"), ("WRLD", "FULL"),
    ("QUST", "FULL"),
}
PAIR = {
    ("MESG", "FULL"): _FULL | {("MESG", "FULL")},
    ("MESG", "ITXT"): _FULL | {("DIAL", "FULL"), ("INFO", "RNAM"), ("MESG", "ITXT")},
    ("MESG", "DESC"): {("MESG", "DESC"), ("NOTE", "TNAM"), ("LSCR", "DESC")},
    ("PERK", "DESC"): {("PERK", "DESC"), ("LSCR", "DESC"), ("SPEL", "DESC")},
    ("PERK", "FULL"): _FULL,
    ("MISC", "FULL"): _FULL,
    ("TERM", "ITXT"): _FULL | {("TERM", "ITXT"), ("TERM", "RNAM")},
    ("TERM", "BTXT"): _FULL | {("TERM", "ITXT"), ("TERM", "RNAM"), ("TERM", "BTXT")},
    ("TERM", "FULL"): _FULL | {("TERM", "RNAM"), ("TERM", "ITXT")},
    ("TERM", "RNAM"): _FULL | {("TERM", "RNAM"), ("TERM", "ITXT")},
    ("TERM", "UNAM"): _FULL | {("TERM", "UNAM"), ("TERM", "RNAM")},
    ("BOOK", "FULL"): _FULL | {("TERM", "ITXT"), ("TERM", "RNAM")},
    ("BOOK", "DESC"): {("NOTE", "FULL"), ("TERM", "ITXT"), ("TERM", "RNAM"), ("BOOK", "FULL")},
}
for _pair in _FULL:
    PAIR.setdefault(_pair, _FULL)


def source_plan_files(game):
    return (
        list(common.PLAN_FILES[game]) +
        ["complete_sst_exact_migration_verified.jsonl.gz",
         "skill_prefix_verified.jsonl.gz", QUEST_FILE] +
        (["ttw_foreign_master_text_verified.jsonl.gz"] if game == "fo3"
         else ["editor_marker_verified.jsonl.gz", "inline_director_cues_verified.jsonl.gz"])
    )


def run(game):
    native = common.module("memory_native", "recover_fnv_xtranslator_origin_verified.py")
    outdir = common.ROOT / "data" / game
    target = common.FO4_DATA / common.ESMS[game]
    expected = json.loads((outdir / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if common.digest(target) != expected:
        raise RuntimeError("Converted ESM SHA256 mismatch")

    planned = {}
    by_text = defaultdict(list)
    for filename in source_plan_files(game):
        for row in common.rows(outdir / filename):
            k = common.field_key(row)
            value = row["english"], row["korean"]
            if k in planned:
                if planned[k] != value:
                    raise ValueError(f"Existing verified plan conflict {k}")
                continue
            planned[k] = value
            by_text[row["english"]].append((
                row["korean"], row["record_type"], row["field"],
                k[0], k[3], filename,
            ))

    candidates = []
    review = []
    report = Counter()
    per_field = Counter()
    for row in common.rows(outdir / "xtranslator_residual_candidates.jsonl.gz"):
        k = row["formid"].upper(), row["record_type"], row["field"], int(row["index"])
        targetpair = k[1:3]
        if k in planned or classify(row)[0] != "actionable" or targetpair not in PAIR:
            continue
        english = row["english"]
        sources = by_text.get(english, [])
        if not sources:
            continue
        translations = {x[0] for x in sources}
        compatible = [x for x in sources if (x[1], x[2]) in PAIR[targetpair]]
        if len(translations) != 1:
            status = "other_verified_plan_has_conflicting_korean"
        elif not compatible:
            status = "no_verified_source_with_semantic_field_compatibility"
        else:
            korean = next(iter(translations))
            if not korean.strip() or korean == english or "\ufffd" in korean:
                status = "empty_or_nonlocalized_korean"
            elif Counter(common.TOKEN.findall(english)) != Counter(common.TOKEN.findall(korean)):
                status = "protected_token_mismatch"
            else:
                status = "verified_existing_translation_reused"
        report[status] += 1
        if status == "verified_existing_translation_reused":
            candidates.append({
                "target_formid": k[0], "record_type": k[1], "field": k[2],
                "target_field_occurrence_index": k[3],
                "english": english, "korean": korean,
                "plan_source": "exact_text_unique_korean_reused_from_verified_conversion_plan",
                "source_evidence": [
                    {
                        "source_converted_formid": s[3],
                        "source_type": s[1], "source_field": s[2],
                        "source_index": s[4], "verified_source_plan": s[5]
                    } for s in sorted(compatible)[:8]
                ],
                "source_evidence_count": len(compatible),
                "verification_note": "Reused exact, whole English and unique verified Korean in compatible display fields. Target runtime semantics still subject to QA.",
            })
            per_field[k[1] + "/" + k[2]] += 1
        else:
            review.append({
                "target_formid": k[0], "record_type": k[1], "field": k[2],
                "index": k[3], "english": english,
                "reason": status, "distinct_korean": len(translations),
                "matching_source_fields": len(compatible),
            })

    grouped = defaultdict(list)
    for r in candidates:
        grouped[int(r["target_formid"], 16)].append(r)
    seen = set()
    for fid, typ, decoded in native.esm_records(target, set(grouped)):
        for r in grouped[fid]:
            k = common.field_key(r)
            if k in seen or typ != k[1] or decoded.get((k[2], k[3])) != r["english"]:
                raise ValueError(f"Target ESM match failed: {k}")
            seen.add(k)
    if len(seen) != len(candidates) or common.digest(target) != expected:
        raise RuntimeError("Target ESM verification incomplete or source changed")

    common.out(outdir / FILE, sorted(candidates, key=common.field_key))
    common.out(outdir / "verified_plan_translation_memory_review.jsonl.gz", review)
    result = {
        "game": game, "target_esm_sha256": expected,
        "source_verified_plan_fields": len(planned),
        "newly_linked": len(candidates), "review": len(review),
        "by_field": dict(per_field), "classification": dict(report),
        "note": "Verified plan memory only. Whole-English exact, unique Korean, whitelisted display roles. ESM and online assets untouched; real runtime contexts still need QA.",
    }
    (outdir / "verified_plan_translation_memory_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(game, "MEMORY_LINKED", len(candidates), "REVIEW", len(review), "BY_FIELD", dict(per_field), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("game", choices=("fo3", "fnv"))
    run(parser.parse_args().game)
