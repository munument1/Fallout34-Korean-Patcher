"""Find recovered FO3 text after Fallout34 relocates it to a different field.

The converter does not expose a complete one-to-one mapping for its generated
INFO, TERM and other records. Do NOT assume a target FormID maps to an original
local ID. Instead, require all of:
  1. A long, byte-verified target English line with an unsatisfied translation;
  2. ONE original, plugin-owned FO3+DLC source record+field containing it (the
     source files are scanned independently, not guessed by converted FormID);
  3. The SAME original record/field/English in the Korean xTranslator SST;
  4. Exactly one valid Korean translation, with protected formatting unchanged;
  5. Independent target ESM FormID/type/field/index/English verification.

Only unambiguous, sufficiently long lines are candidates. No ESM copies, game
edits, or F34Online changes. Lack of exact source FormID link means these are
cross-field high-confidence text matches, *not* a proven converter-origin map.
Store the exact source evidence for further contextual review.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fo3"
SOURCE_DIR = Path(r"C:\Games\Steam\steamapps\common\Fallout 3 goty\Data")
TARGET_ESM = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm")
SST = Path("F:/번역/프로그램/xTranslator/UserDictionaries/FalloutNV")
SOURCE_NAMES = ("fallout3", "anchorage", "thepitt", "brokensteel", "pointlookout", "zeta")
ACTIVE_PLANS = (
    "indexed_patch_plan_candidates.jsonl.gz",
    "indexed_patch_plan_v2_strict_extra.jsonl.gz",
    "xtranslator_verified_visible_extra.jsonl.gz",
    "manual_visible_translation_verified.jsonl.gz",
    "sibling_info_field_verified.jsonl.gz",
    "import_manifest_migrated_verified.jsonl.gz",
)
TARGET_FIELDS = {
    ("INFO", "NAM1"),
    ("INFO", "RNAM"),
    ("TERM", "ITXT"),
    ("TERM", "UNAM"),
    ("TERM", "BTXT"),
    ("TERM", "RNAM"),
    ("TERM", "FULL"),
    ("MESG", "DESC"),
    ("MESG", "ITXT"),
    ("QUST", "CNAM"),
    ("PERK", "DESC"),
}
SOURCE_TYPES = {
    b"INFO", b"DIAL", b"TERM", b"NOTE", b"MESG", b"QUST", b"PERK",
    b"BOOK", b"MISC", b"NPC_", b"WEAP", b"ARMO",
}
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)
MIN_ENGLISH_LENGTH = 40


def load(path):
    with gzip.open(path, "rt", encoding="utf8") as fp:
        for line in fp:
            yield json.loads(line)


def save(path, entries):
    with gzip.open(path, "wt", encoding="utf8", compresslevel=6) as fp:
        for row in entries:
            fp.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def modules():
    def imp(name, filename):
        spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / filename)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    return (
        imp("cross_field_sst", "read_xtranslator_sst.py"),
        imp("cross_field_source", "recover_fo3_xtranslator_provenance.py"),
        imp("cross_field_native", "recover_fnv_xtranslator_origin_verified.py"),
    )


def verify_target(native, plan):
    selected = defaultdict(list)
    for row in plan:
        selected[int(row["target_formid"], 16)].append(row)
    found = set()
    for fid, typ, fields in native.esm_records(TARGET_ESM, set(selected)):
        for row in selected[fid]:
            key = (
                row["target_formid"], row["record_type"], row["field"],
                row["target_field_occurrence_index"],
            )
            if typ != row["record_type"] or fields.get((row["field"], key[3])) != row["english"]:
                raise RuntimeError(f"Wrong target ESM field: {key}")
            if key in found:
                raise RuntimeError(f"Duplicate target ESM field: {key}")
            found.add(key)
    if len(found) != len(plan):
        raise RuntimeError(f"Target ESM missing {len(plan)-len(found)} proposed fields")


def run():
    sst_reader, fo3, native = modules()
    expected = json.loads((DATA / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if fo3.hash_file(TARGET_ESM) != expected:
        raise RuntimeError("FO3 converted ESM SHA256 differs from translation plan")
    already = {}
    for name in ACTIVE_PLANS:
        for row in load(DATA / name):
            key = (row["target_formid"], row["record_type"], row["field"],
                   int(row["target_field_occurrence_index"]))
            v = (row["english"], row["korean"])
            if key in already and already[key] != v:
                raise RuntimeError(f"Existing plan conflict {key}")
            already[key] = v
    potential = set()
    for row in load(DATA / "generated_source_match_candidates.jsonl.gz"):
        if row.get("source_candidates_count") != 1:
            continue
        typ, field = row["record_type"], row["field"]
        english = row["english"]
        if (typ, field) in TARGET_FIELDS and len(english.strip()) >= MIN_ENGLISH_LENGTH:
            potential.add((row["target_formid"], typ, field, english))
    # Only fields in the current xTranslator extraction are relevant. Gather
    # the same line at multiple target indices without guessing its position.
    unlinked = defaultdict(list)
    for row in load(DATA / "xtranslator_residual_candidates.jsonl.gz"):
        signature = row["formid"], row["record_type"], row["field"], row["english"]
        targetkey = (*signature[:3], int(row["index"]))
        if signature not in potential or targetkey in already:
            continue
        if row["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        if row["conditional_proc"] is not None or row["priority"] != "P0":
            continue
        unlinked[signature].append(row)
    needed = {x[3] for x in unlinked}
    if not needed:
        raise RuntimeError("No eligible long source lines to investigate")
    source_occurrences = defaultdict(set)
    source_sha = {}
    original_indices = defaultdict(set)
    # The native ESMs must be independently scanned, including all source
    # string fields in the eligible source record types. Filter overrides.
    for name in SOURCE_NAMES:
        p = SOURCE_DIR / (name + ".esm")
        owner_index = native.original_owner_index(p)
        for fp, at, n, flags, fid, typ in fo3.records(p):
            if typ.encode("ascii", "replace") not in SOURCE_TYPES:
                continue
            if fid >> 24 != owner_index:
                continue
            fields = fo3.fields(fo3.read_record(fp, at, n, flags))
            for field, index, raw in fields:
                english = fo3.decode(raw)
                if english in needed:
                    original_indices[(name + ".esm", fid & 0xFFFFFF, typ, field, english)].add(index)
                    source_occurrences[english].add((name + ".esm", fid & 0xFFFFFF, typ, field))
        source_sha[name + ".esm"] = fo3.hash_file(p)

    reader = sst_reader
    sst_lines = defaultdict(set)
    sst_hashes = {}
    for name in SOURCE_NAMES:
        path = SST / (name + "_en_ko.sst")
        parsed = reader.parse_sst(path)
        sst_hashes[path.name] = parsed["sha256"]
        masters = [m.casefold() for m in parsed["master_files"]]
        for row in parsed["records"]:
            form = int(row["form_id"], 16)
            if form >> 24 >= len(masters):
                continue
            owner = masters[form >> 24]
            local = form & 0xFFFFFF
            k = owner, local, row["record_name"], row["field_name"], row["source"]
            if k not in original_indices or not row["korean"] or row["korean"] == row["source"]:
                continue
            if row["index"] not in original_indices[k]:
                continue
            sst_lines[k].add((row["korean"], path.name, int(row["index"])))
    verified, review = [], []
    classes = Counter()
    migrations = Counter()
    for signature, target_rows in unlinked.items():
        target_formid, target_type, target_field, english = signature
        origins = source_occurrences.get(english, set())
        if not origins:
            state = "no_original_source_line"
        elif len(origins) != 1:
            state = "multiple_source_records_or_fields"
        else:
            origin = next(iter(origins))
            source_plugin, local, source_type, source_field = origin
            matching = sst_lines.get((source_plugin, local, source_type, source_field, english), set())
            korean_choices = {k for k, _, _ in matching}
            if not matching:
                state = "original_field_untranslated_in_sst"
            elif len(korean_choices) != 1:
                state = "original_field_has_conflicting_korean"
            else:
                korean = next(iter(korean_choices))
                if "\ufffd" in korean or Counter(TOKEN.findall(english)) != Counter(TOKEN.findall(korean)):
                    state = "format_or_encoding_invalid"
                elif not korean.strip():
                    state = "empty_korean"
                else:
                    state = "unique_original_text_field_sst_verified"
        classes[state] += len(target_rows)
        if state == "unique_original_text_field_sst_verified":
            for row in target_rows:
                verified.append({
                    "target_formid": target_formid,
                    "record_type": target_type,
                    "field": target_field,
                    "target_field_occurrence_index": int(row["index"]),
                    "english": english,
                    "korean": korean,
                    "plan_source": "fo3_single_unique_original_esm_long_text_sst_migration",
                    "previous_unlinked_class": row["status"],
                    "source_evidence": {
                        "plugin": source_plugin,
                        "source_local_formid": f"{local:06X}",
                        "source_record_type": source_type,
                        "source_field": source_field,
                        "source_sst_entries": [
                            {"sst": p, "source_index": idx} for ko, p, idx in sorted(matching)
                        ],
                        "migration": f"{source_type}/{source_field}->{target_type}/{target_field}",
                        "match_type": "globally_unique_original_long_text_not_direct_formid_link",
                    },
                })
                migrations[(source_type, source_field, target_type, target_field)] += 1
        else:
            review.append({
                "target_formid": target_formid,
                "target_type": target_type, "target_field": target_field,
                "english": english, "occurrences": len(target_rows),
                "reason": state, "original_match_count": len(origins),
                "sample_source": [f"{p}:{fid:06X}:{typ}/{field}" for p, fid, typ, field in sorted(origins)[:4]],
            })
    verify_target(native, verified)
    if fo3.hash_file(TARGET_ESM) != expected:
        raise RuntimeError("FO3 converted source changed during validation")
    verified.sort(key=lambda r: (r["target_formid"], r["record_type"], r["field"],
                                 r["target_field_occurrence_index"]))
    save(DATA / "cross_field_long_text_verified.jsonl.gz", verified)
    save(DATA / "cross_field_long_text_review.jsonl.gz", review)
    report = {
        "game": "fo3",
        "scope": "long >=40 character P0 ESM screen fields, current residuals with no plan",
        "target_esm_sha256": expected,
        "original_source_esm_hashes": source_sha,
        "original_korean_sst_hashes": sst_hashes,
        "potential_source_lines": len(needed),
        "remaining_fields_checked": sum(map(len, unlinked.values())),
        "new_text_assignments_verified": len(verified),
        "classes": dict(classes),
        "source_to_target_field_migrations": {
            f"{x[0]}/{x[1]} -> {x[2]}/{x[3]}": n
            for x, n in migrations.most_common()
        },
        "warning": "Cross-field text-only high-confidence provenance, not an exact FormID converter mapping. Source strings are original-unique, but actual gameplay context and speaker still need review. No ESM or patch emitted.",
    }
    (DATA / "cross_field_long_text_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print("FO3", "NEW", len(verified), "CHECKED", sum(map(len, unlinked.values())),
          "MIGRATIONS", migrations.most_common(20), "COUNTS", classes, flush=True)


if __name__ == "__main__":
    run()
