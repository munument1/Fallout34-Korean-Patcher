"""Repair Fallout34 converter-migrated INFO NAM1/RNAM translations within one record.

Only an original-string-identical sibling INFO field within the *same converted
FormID* may donate its verified Korean. RNAM is the dialogue choice, NAM1
is the spoken response/subtitle. This is distinct from unsafe global English
translation-memory matching.

Reads pinned ESM hash and prior versioned assignment plans. Generates ONLY
unapplied data assignments. No ESM/ESP copies, writes, or game deployment.
"""
from collections import defaultdict, Counter
from pathlib import Path
import gzip
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
SOURCE_PLANS = (
    "indexed_patch_plan_candidates.jsonl.gz",
    "indexed_patch_plan_v2_strict_extra.jsonl.gz",
    "xtranslator_verified_visible_extra.jsonl.gz",
    "manual_visible_translation_verified.jsonl.gz",
)
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)


def records(path):
    with gzip.open(path, "rt", encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def key(row):
    return (
        row["target_formid"],
        row["record_type"],
        row["field"],
        int(row["target_field_occurrence_index"]),
    )


def main():
    for game in ("fo3", "fnv"):
        d = DATA / game
        esm_file = SOURCE / ("Fallout34.esm" if game == "fo3" else "FalloutNV34.esm")
        expected = json.loads((d / "indexed_plan_report.json").read_text("utf-8"))["esm_sha256"]
        if digest(esm_file) != expected:
            raise RuntimeError(f"{game}: current ESM is not the source version validated")
        known = {}
        siblings = defaultdict(set)
        for filename in SOURCE_PLANS:
            for row in records(d / filename):
                k = key(row)
                value = row["english"], row["korean"]
                if k in known and known[k] != value:
                    raise RuntimeError(f"{game} inconsistent source plan {k}")
                known[k] = value
                if row["record_type"] == "INFO" and row["field"] in ("NAM1", "RNAM"):
                    siblings[(row["target_formid"], row["english"])].add(
                        (row["field"], row["korean"], filename, k)
                    )
        assignments = []
        seen = set()
        rejection = Counter()
        by_field = defaultdict(Counter)
        for row in records(d / "xtranslator_residual_candidates.jsonl.gz"):
            if row["record_type"] != "INFO" or row["field"] not in ("NAM1", "RNAM"):
                continue
            if row["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
                continue
            k = (row["formid"], row["record_type"], row["field"], int(row["index"]))
            if k in known:
                rejection["already_covered"] += 1
                continue
            if k in seen:
                raise RuntimeError(f"Duplicate residual at {k}")
            seen.add(k)
            source = [
                (korean, filename, origin)
                for field, korean, filename, origin in siblings.get((row["formid"], row["english"]), ())
                if field != row["field"]
            ]
            korean_values = {x[0] for x in source}
            if not source:
                rejection["no_identical_translated_sibling_in_same_formid"] += 1
                continue
            if len(korean_values) != 1:
                rejection["conflicting_sibling_translations"] += 1
                continue
            korean = next(iter(korean_values))
            if not korean or "\ufffd" in korean or korean == row["english"] or not korean.strip():
                rejection["invalid_sibling_korean"] += 1
                continue
            if Counter(TOKEN.findall(row["english"])) != Counter(TOKEN.findall(korean)):
                rejection["placeholder_mismatch"] += 1
                continue
            source_english = {known[proof][0] for _, _, proof in source}
            if source_english != {row["english"]}:
                raise RuntimeError("Inconsistent sibling source English")
            assignments.append({
                "target_formid": row["formid"],
                "record_type": "INFO",
                "field": row["field"],
                "target_field_occurrence_index": row["index"],
                "english": row["english"],
                "korean": korean,
                "plan_source": "same_converted_info_formid_identical_translated_sibling_field",
                "evidence": [
                    {"sibling_field": proof[2], "sibling_index": proof[3],
                     "sibling_source_plan": filename}
                    for _, filename, proof in sorted(source)
                ],
                "previous_unlinked_class": row["status"],
            })
            by_field[row["field"]][row["status"]] += 1
        assignments.sort(key=key)
        if digest(esm_file) != expected:
            raise RuntimeError(f"{game}: target ESM changed during proof")
        output = d / "sibling_info_field_verified.jsonl.gz"
        with gzip.open(output, "wt", encoding="utf8", compresslevel=6) as fp:
            for row in assignments:
                fp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        summary = {
            "game": game,
            "source_esm_sha256": expected,
            "restored_unique_field_occurrences": len(assignments),
            "restored_by_field_and_original_status": {f: dict(c) for f, c in by_field.items()},
            "rejected": dict(rejection),
            "algorithm": "same converted FormID, INFO, exact original English; unique Korean from the already version-validated opposite field RNAM/NAM1",
            "warning": "Only translation assignments produced. No game ESM changed or copied. In-game QA remains necessary.",
        }
        (d / "sibling_info_field_report.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
        )
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
