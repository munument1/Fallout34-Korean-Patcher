"""Report CURRENT Fallout34 *translation work*, never blank/editor field totals.

The only user-facing missing-translation count is an actionable shortlist of
nonempty text in player-facing fields. It deliberately omits whitespace,
symbols, Fallout4 master fields, likely editor IDs and uncertain visibility.
Retain low-level audit detail separately, but do not present it as missing
translation work. No game asset is changed by this script.
"""
from collections import defaultdict, Counter
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
from translation_work_filter import classify as work_classify

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
        "complete_sst_exact_migration_verified.jsonl.gz",
        "ttw_foreign_master_text_verified.jsonl.gz",
        "skill_prefix_verified.jsonl.gz",
    ),
    "fnv": (
        "import_manifest_migrated_verified.jsonl.gz",
        "fnv_cross_field_long_text_verified.jsonl.gz",
        "complete_sst_exact_migration_verified.jsonl.gz",
        "skill_prefix_verified.jsonl.gz",
        "editor_marker_verified.jsonl.gz",
        "inline_director_cues_verified.jsonl.gz",
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
        translation_work = defaultdict(lambda: {"count": 0, "ids": []})
        work_by_field = Counter()
        work_by_status = Counter()
        withheld_by_reason = Counter()
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
            work_class, work_reason = work_classify(row)
            if work_class == "actionable":
                signature = (state, row["record_type"], row["field"], row["english"])
                task = translation_work[signature]
                task["count"] += 1
                if len(task["ids"]) < 8:
                    task["ids"].append(row["formid"])
                work_by_field[row["record_type"] + "/" + row["field"]] += 1
                work_by_status[state] += 1
            else:
                # Forensics only. Never present this in an untranslated count.
                withheld_by_reason[work_reason] += 1
        dest = d / "current_unlinked_display_review.csv"
        # Keep the familiar file name for downstream users, but strictly
        # exclude blanks, other-game masters and editor/runtime-review data.
        # No automatic translation is applied from mere English matches.
        work_dest = d / "current_translation_work_items.csv"
        for path in (dest, work_dest):
            with path.open("w", encoding="utf-8-sig", newline="") as fp:
                writer = csv.writer(fp)
                writer.writerow(["work","status","record_type","field","occurrences","english_json","example_formids"])
                for (status, typ, field, english), task in sorted(
                        translation_work.items(),
                        key=lambda item:(-item[1]["count"], item[0][1], item[0][2], item[0][3])):
                    writer.writerow([
                        "source_translation_lookup" if status == "missing_translation_match"
                        else "link_existing_korean_with_context",
                        status, typ, field, task["count"],
                        json.dumps(english, ensure_ascii=False), ";".join(task["ids"])
                    ])
        work_report = {
            "game": game,
            "esm_sha256": expected,
            "translation_work_item_occurrences": sum(work_by_field.values()),
            "distinct_type_field_english_work_items": len(translation_work),
            "work_by_type_field": dict(sorted(work_by_field.items(), key=lambda i:-i[1])),
            "work_by_source_status": dict(work_by_status),
            "work_csv": work_dest.name,
            "in_game_visibility_confirmed_for_every_item": False,
            "note": (
                "Only nonempty human-readable strings on player-facing field types; "
                "excludes FO4 master content, empty strings, numeric/symbol content, "
                "obvious editor IDs and unclear runtime fields. These are prioritized "
                "translation/linking review items, NOT verified runtime untranslated "
                "lines. No count of blank/internal fields is a translation task."
            ),
        }
        (d / "current_translation_work_report.json").write_text(
            json.dumps(work_report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
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
            "user_facing_translation_work_report": "current_translation_work_report.json",
            "user_facing_translation_work_csv": work_dest.name,
            "user_facing_translation_work_occurrences": work_report["translation_work_item_occurrences"],
            "warning": "Static field inventory only, not precise in-game untranslated count. Editor/special field classification is conservative. Existing Korean needing a context link is NOT regarded as solved. No original or translated ESM was generated or altered.",
        }
        (d / "current_unlinked_esm_report.json").write_text(
            json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
        print(game, "TRANSLATION_WORK", work_report["translation_work_item_occurrences"],
              "DISTINCT", len(translation_work),
              "SOURCE_STATUS", dict(work_by_status),
              "BY_FIELD", work_by_field.most_common(20),
              "RUNTIME_CONFIRMATION", "pending", flush=True)


if __name__ == "__main__":
    main()
