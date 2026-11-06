"""Recount CURRENT Fallout34 ESM localization gaps after all verified recovery plans.

Do not conflate field occurrences with unique lines or in-game reachable text.
Categorizes non-content blanks and obvious editor/conditional fields separately.
Never changes or generates an ESM or ESP. No online-module/FO4 base scanning.
"""
from collections import defaultdict, Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
PLANS = (
    "indexed_patch_plan_candidates.jsonl.gz",
    "indexed_patch_plan_v2_strict_extra.jsonl.gz",
    "xtranslator_verified_visible_extra.jsonl.gz",
    "manual_visible_translation_verified.jsonl.gz",
    "sibling_info_field_verified.jsonl.gz",
)
MIGRATED_PLANS = {
    "fo3": (
        "import_manifest_migrated_verified.jsonl.gz",
        "cross_field_long_text_verified.jsonl.gz",
    ),
    "fnv": (
        "import_manifest_migrated_verified.jsonl.gz",
        "fnv_cross_field_long_text_verified.jsonl.gz",
    ),
}
DIRECT = {
    ("INFO", "NAM1"), ("INFO", "RNAM"),
    ("TERM", "ITXT"), ("TERM", "BTXT"), ("TERM", "UNAM"),
    ("TERM", "RNAM"), ("TERM", "FULL"),
    ("MESG", "ITXT"), ("MESG", "DESC"), ("MESG", "FULL"),
    ("QUST", "CNAM"), ("LSCR", "DESC"),
    ("BOOK", "DESC"), ("BOOK", "FULL"),
}
POSSIBLE = {
    ("NPC_", "FULL"), ("WEAP", "FULL"), ("ARMO", "FULL"),
    ("AMMO", "FULL"), ("MISC", "FULL"), ("ALCH", "FULL"),
    ("KEYM", "FULL"), ("CELL", "FULL"), ("WRLD", "FULL"),
    ("PERK", "FULL"), ("PERK", "DESC"), ("NOTE", "DESC"),
    ("CONT", "FULL"), ("ACTI", "FULL"), ("FURN", "FULL"),
    ("DOOR", "FULL"), ("FACT", "FULL"), ("TACT", "FULL"),
}
SUSPECT_EDITOR = {
    ("QUST", "FULL"), ("NOTE", "FULL"), ("TERM", "WNAM"),
    ("QUST", "NNAM"), ("MGEF", "FULL"), ("SPEL", "FULL"),
    ("SPEL", "DESC"), ("PERK", "EPFD"), ("REFR", "FULL"),
    ("ENCH", "FULL"), ("HAZD", "FULL"), ("EXPL", "FULL"),
}


def load(path):
    with gzip.open(path, "rt", encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)


def key(row, from_residual=False):
    return (
        row["formid"] if from_residual else row["target_formid"],
        row["record_type"],
        row["field"],
        int(row["index"] if from_residual else row["target_field_occurrence_index"]),
    )


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def category(row):
    # Fallout34.esm and FalloutNV34.esm reference their Fallout4.esm
    # master with load-order index 00. These are NOT FO3/FNV strings to
    # retranslate, even when xTranslator includes them as English text.
    if int(row["formid"], 16) >> 24 == 0:
        return "external_fallout4_master_record"
    text = row["english"]
    if not text.strip():
        return "non_content_whitespace"
    if not any(c.isalnum() for c in text):
        return "non_content_symbols"
    pair = row["record_type"], row["field"]
    if row["conditional_proc"] is not None:
        return "conditional_field_needs_procedure_review"
    if pair in DIRECT:
        return "direct_screen_text_candidate"
    if pair in POSSIBLE:
        return "gameplay_name_or_description_candidate"
    if pair in SUSPECT_EDITOR:
        return "editor_or_special_field_needs_runtime_check"
    return "other_field_needs_runtime_check"


def main():
    for game in ("fo3", "fnv"):
        d = ROOT / "data" / game
        esm = SOURCE / ("Fallout34.esm" if game == "fo3" else "FalloutNV34.esm")
        expected = json.loads((d / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
        if digest(esm) != expected:
            raise RuntimeError(f"{game}: installed ESM not version pinned")
        planned = {}
        per_plan = Counter()
        for name in (*PLANS, *MIGRATED_PLANS[game]):
            for r in load(d / name):
                k = key(r)
                value = (r["english"], r["korean"])
                if k in planned and planned[k] != value:
                    raise RuntimeError(f"{game}: conflicting assignment across plans {k}")
                if k not in planned:
                    planned[k] = value
                    per_plan[name] += 1
        states = Counter()
        categories = defaultdict(Counter)
        candidates = defaultdict(lambda: {"count": 0, "ids": [], "state": "", "class": ""})
        for row in load(d / "xtranslator_residual_candidates.jsonl.gz"):
            k = key(row, from_residual=True)
            if k in planned:
                if planned[k][0] != row["english"]:
                    raise RuntimeError(f"{game}: assigned English differs from residual {k}")
                states["resolved_by_new_plan"] += 1
                continue
            cls = category(row)
            state = row["status"]
            states[f"unlinked_{state}"] += 1
            states[f"unlinked_{cls}"] += 1
            categories[row["record_type"] + "/" + row["field"]][state + ":" + cls] += 1
            signature = (cls, state, row["record_type"], row["field"], row["english"])
            cell = candidates[signature]
            cell["count"] += 1
            cell["state"] = state
            cell["class"] = cls
            if len(cell["ids"]) < 4:
                cell["ids"].append(row["formid"])
        dest = d / "current_unlinked_display_review.csv"
        # Individual type/field/English grouping does not imply all contexts share
        # one safe Korean translation. This is a *review* shortlist, not a plan.
        with dest.open("w", encoding="utf-8-sig", newline="") as fp:
            writer = csv.writer(fp)
            writer.writerow(["group","status","record_type","field","occurrences","english_json","example_formids"])
            for (cls, status, typ, field, english), c in sorted(
                    candidates.items(), key=lambda x:(x[0][0], -x[1]["count"], x[0][2], x[0][3])):
                writer.writerow([cls, status, typ, field, c["count"],
                                 json.dumps(english, ensure_ascii=False), ";".join(c["ids"])])
        final = {
            "game": game,
            "esm_sha256": expected,
            "translation_plan_rows_total": len(planned),
            "rows_by_plan": dict(per_plan),
            "xtranslator_current_unlinked_occurrence_states": dict(states),
            "unlinked_distinct_type_field_english_by_class": dict(
                Counter({cls: sum(1 for k in candidates if k[0] == cls)
                         for cls in {k[0] for k in candidates}})
            ),
            "by_type_field_and_current_state": {k: dict(v) for k, v in sorted(categories.items())},
            "review_csv": dest.name,
            "warning": "Static field inventory only, not precise in-game untranslated count. Editor/special field classification is conservative. Existing Korean needing a context link is NOT regarded as solved. No original or translated ESM was generated or altered.",
        }
        (d / "current_unlinked_esm_report.json").write_text(
            json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
        short = {k:v for k,v in states.items() if k.startswith("unlinked_") and (
            k in ("unlinked_missing_translation_match","unlinked_existing_korean_needs_context")
            or k in ("unlinked_direct_screen_text_candidate","unlinked_gameplay_name_or_description_candidate",
                     "unlinked_editor_or_special_field_needs_runtime_check","unlinked_non_content_whitespace",
                     "unlinked_non_content_symbols"))}
        print(game, "PLAN", len(planned), "UNLINKED", short,
              "UNIQUE", final["unlinked_distinct_type_field_english_by_class"], flush=True)


if __name__ == "__main__":
    main()
