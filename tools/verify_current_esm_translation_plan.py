"""Independent READ-ONLY verification of *all* current ESM translation assignments.

No ESM copies or installer writes. Validates exact target FormID, type, field
index, source English and protected formatting tokens in every planned row.
This is a static safety check, not a substitute for finding untranslated lines.
"""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re

from build_localized_esm_copy import load_assignments, sha256
from verify_localized_esm_copy import events, subrecords

ROOT = Path(__file__).resolve().parents[1]
GAME_DATA = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
EXTRAS = [
    "xtranslator_verified_visible_extra.jsonl.gz",
    "manual_visible_translation_verified.jsonl.gz",
    "sibling_info_field_verified.jsonl.gz",
]
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)


def decode(raw):
    if not raw or b"\0" in raw[:-1]:
        return None
    source = raw[:-1] if raw.endswith(b"\0") else raw
    for encoding in ("utf8", "cp1252"):
        try:
            return source.decode(encoding)
        except UnicodeError:
            continue
    return None


def verify(game):
    folder = ROOT / "data" / game
    esm = GAME_DATA / ("Fallout34.esm" if game == "fo3" else "FalloutNV34.esm")
    expected = json.loads((folder / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if sha256(esm) != expected:
        raise ValueError(f"{game}: installed ESM no longer matches pinned revision")
    assignments, plan_counts = load_assignments(folder, [folder / x for x in EXTRAS])
    by_record = defaultdict(dict)
    for (fid, typ, field, idx), (english, korean) in assignments.items():
        if Counter(TOKEN.findall(english)) != Counter(TOKEN.findall(korean)):
            raise RuntimeError(f"Protected token mismatch at {fid:08X} {typ}/{field}:{idx}")
        by_record[(fid, typ)][field, idx] = (english, korean)
    found = set()
    tally = Counter()
    for row in events(esm):
        if row[0] != "record":
            continue
        (tag, fid, _, _, _), contents = row[1], row[2]
        typ = tag.decode("ascii", "replace")
        batch = by_record.get((fid, typ))
        if batch is None:
            continue
        for (field, idx), raw in subrecords(contents):
            if (field, idx) not in batch:
                continue
            key = fid, typ, field, idx
            english, _ = batch[field, idx]
            if decode(raw) != english:
                raise ValueError(f"{game}: source changed at {key}")
            if key in found:
                raise ValueError(f"Duplicate target in source at {key}")
            found.add(key)
            tally[f"{typ}/{field}"] += 1
    if len(found) != len(assignments):
        missing = list(assignments.keys() - found)
        raise RuntimeError(f"{game}: missing {len(missing)} assignments: sample {missing[:5]}")
    if sha256(esm) != expected:
        raise RuntimeError("Source ESM changed during audit")
    report = {
        "game": game,
        "esm_sha256": expected,
        "source_record_field_matches": len(found),
        "source_plan_rows": dict(plan_counts),
        "field_match_counts": dict(tally),
        "verification": "PASS static source ESM assignment and placeholder invariants",
        "warning": "NO ESM copied, installed, overwritten, or generated. Many in-game English strings remain unlinked or untranslated.",
    }
    (folder / "current_translation_plan_verify.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(game, "SOURCE_VERIFIED", len(found), "BY_PLAN", plan_counts, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("game", choices=("fo3", "fnv"))
    verify(parser.parse_args().game)
