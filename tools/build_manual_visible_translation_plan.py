"""Fill proven unassigned FO3/FNV ESM screen-text gaps from an explicit Korean glossary.

No conversion/ESM copy generation. Translation rows are applied only when:
 * pinned installed ESM matches the snapshot SHA256,
 * exact English and record type/field are present in xTranslator residuals,
 * a manual Korean phrase is supplied and format tokens match, and
 * the assignment does not overlap an earlier plan.

Universal short/common phrases are translated consistently only within their
explicit record field. Context-specific dialog gets FormID-specific entries in
a future batch, never a guessed global English-to-Korean dictionary.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ESM_FOLDER = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)
GLOSSARY = DATA / "manual_visible_glossary_ko.json"


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as file:
        for line in file:
            yield json.loads(line)


def key(row):
    return (row["target_formid"], row["record_type"], row["field"], int(row["target_field_occurrence_index"]))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    for game in ("fo3", "fnv"):
        d = DATA / game
        expected = json.loads((d / "indexed_plan_report.json").read_text("utf-8"))["esm_sha256"]
        esm = ESM_FOLDER / ("Fallout34.esm" if game == "fo3" else "FalloutNV34.esm")
        if digest(esm) != expected:
            raise RuntimeError(f"{game}: installed ESM version changed")
        translated = {}
        for fname in (
            "indexed_patch_plan_candidates.jsonl.gz",
            "indexed_patch_plan_v2_strict_extra.jsonl.gz",
            "xtranslator_verified_visible_extra.jsonl.gz",
        ):
            for r in load(d / fname):
                k = key(r)
                if k in translated and translated[k] != (r["english"], r["korean"]):
                    raise RuntimeError(f"{game}: source plan conflict {k}")
                translated[k] = (r["english"], r["korean"])
        terms = {}
        for row in glossary[game]:
            signature = (row["record_type"], row["field"], row["english"])
            korean = row["korean"]
            if signature in terms:
                raise RuntimeError(f"Duplicate glossary string: {signature}")
            if not korean.strip() or korean == row["english"] or "\ufffd" in korean:
                raise RuntimeError(f"Invalid Korean: {signature}")
            if Counter(TOKEN.findall(row["english"])) != Counter(TOKEN.findall(korean)):
                raise RuntimeError(f"Format token difference: {signature}")
            terms[signature] = korean
        rows = []
        discovered = Counter()
        seen = set()
        previously_covered = Counter()
        for r in load(d / "xtranslator_residual_candidates.jsonl.gz"):
            if r["status"] != "missing_translation_match":
                continue
            sig = (r["record_type"], r["field"], r["english"])
            if sig not in terms or r["priority"] != "P0" or r["conditional_proc"] is not None:
                continue
            k = (r["formid"], r["record_type"], r["field"], int(r["index"]))
            if k in translated:
                previously_covered[sig] += 1
                # Existing source-backed translation takes precedence.
                continue
            if k in seen:
                raise RuntimeError(f"Duplicate manual candidate {k}")
            seen.add(k)
            discovered[sig] += 1
            rows.append({
                "target_formid": r["formid"],
                "record_type": r["record_type"],
                "field": r["field"],
                "target_field_occurrence_index": r["index"],
                "english": r["english"],
                "korean": terms[sig],
                "plan_source": "manual_screen_phrase_explicit_review",
                "review_scope": "exact game + record type + field + English",
            })
        misses = set(terms) - set(discovered) - set(previously_covered)
        if misses:
            raise RuntimeError(f"Manual glossary phrases not found in current {game} ESM residuals: {sorted(misses)[:12]}")
        rows.sort(key=key)
        if digest(esm) != expected:
            raise RuntimeError("ESM changed during planning")
        outfile = d / "manual_visible_translation_verified.jsonl.gz"
        with gzip.open(outfile, "wt", encoding="utf-8", compresslevel=6) as out:
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        report = {
            "game": game,
            "esm_sha256": expected,
            "manual_english_phrases": len(terms),
            "newly_reconnected_field_occurrences": len(rows),
            "already_covered_with_provenance": sum(previously_covered.values()),
            "by_record_field": dict(Counter(f"{r['record_type']}/{r['field']}" for r in rows)),
            "manual_source": str(GLOSSARY.relative_to(ROOT)),
            "warning": "This adds text assignments to the translation backlog. It does NOT create a new ESM, modify game installation, prove actual runtime display, or assert complete translation.",
        }
        (d / "manual_visible_translation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
