"""Promote provenance-checked visible text, not raw xTranslator 'translatable' matches.

FO3 and NV original ESM/SST identity must already have been proven by the source
recovery scripts. In addition to that proof, this script verifies that each
candidate is missing from the existing plans and belongs to a likely runtime
visible, unconditional xTranslator field. Other fields remain review-only.

Do not read or modify F34Online.esp, other mods, or game installation assets.
"""
from collections import Counter
from pathlib import Path
import gzip
import json
import re

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_FIELDS = {
    ("INFO", "NAM1"),   # NPC subtitle
    ("TERM", "ITXT"),   # Terminal choice
    ("TERM", "RNAM"),   # Terminal loading/status text
    ("MESG", "ITXT"),   # Message choice
    ("QUST", "CNAM"),   # Quest objective text
}
SOURCES = {
    "fo3": "xtranslator_fo3_provenance_exact.jsonl.gz",
    "fnv": "xtranslator_fallback_source_verified.jsonl.gz",
}
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as fp:
        for line in fp:
            yield json.loads(line)


def key(r):
    return (
        r["target_formid"].upper(), r["record_type"], r["field"],
        int(r["target_field_occurrence_index"]),
    )


def main():
    for game in ("fo3", "fnv"):
        d = ROOT / "data" / game
        used = {}
        for filename in (
            "indexed_patch_plan_candidates.jsonl.gz",
            "indexed_patch_plan_v2_strict_extra.jsonl.gz",
        ):
            for row in load(d / filename):
                k = key(row)
                if k in used and used[k] != (row["english"], row["korean"]):
                    raise RuntimeError(f"{game}: contradictory base translations {k}")
                used[k] = row["english"], row["korean"]
        residual = {}
        for row in load(d / "xtranslator_residual_candidates.jsonl.gz"):
            if row["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
                continue
            k = row["formid"].upper(), row["record_type"], row["field"], int(row["index"])
            if k in residual:
                raise RuntimeError(f"{game}: duplicate xTranslator residual {k}")
            residual[k] = row
        accepted, deferred = [], []
        reasons = Counter()
        seen = set()
        for row in load(d / SOURCES[game]):
            k = key(row)
            if k in seen:
                raise RuntimeError(f"{game}: duplicate proven target {k}")
            seen.add(k)
            entry = residual.get(k)
            if entry is None or entry["english"] != row["english"]:
                raise RuntimeError(f"{game}: source candidate is not in current residual {k}")
            if row.get("xtranslator_input_status", entry["status"]) != entry["status"]:
                raise RuntimeError(f"{game}: xTranslator input status differs at {k}")
            if k in used:
                raise RuntimeError(f"{game}: source candidate collides with active translation {k}")
            if (row["record_type"], row["field"]) not in ALLOWED_FIELDS:
                reason = "display_reachability_not_established"
            elif entry.get("conditional_proc") is not None:
                reason = "conditional_xtranslator_proc"
            elif entry.get("priority") != "P0":
                reason = "not_p0"
            elif not row.get("korean") or not row["korean"].strip() or row["korean"] == row["english"]:
                reason = "not_translated"
            elif "\ufffd" in row["korean"]:
                reason = "replacement_character"
            elif Counter(TOKEN.findall(row["english"])) != Counter(TOKEN.findall(row["korean"])):
                reason = "placeholder_mismatch"
            else:
                reason = ""
            if reason:
                reasons[reason] += 1
                deferred.append({**row, "review_reason": reason})
            else:
                accepted.append(row)
                reasons["promoted_verified_visible"] += 1
        accepted.sort(key=key)
        for path, rows in (
            (d / "xtranslator_verified_visible_extra.jsonl.gz", accepted),
            (d / "xtranslator_verified_visible_deferred.jsonl.gz", deferred),
        ):
            with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as fp:
                for row in rows:
                    fp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        report = {
            "game": game,
            "original_source_file": SOURCES[game],
            "base_plan_fields": len(used),
            "source_verified_candidates": len(seen),
            "promoted_display_priority": len(accepted),
            "deferred": len(deferred),
            "by_reason": dict(reasons),
            "promoted_by_field": dict(Counter(r["record_type"] + "/" + r["field"] for r in accepted)),
            "scope": "ESM-based FO3/FNV content only; no F34Online, ESL carrier or game file touched",
            "warning": "FO4 in-game display and text layout still need playtesting. This does not establish completed translation.",
        }
        (d / "xtranslator_verified_visible_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
