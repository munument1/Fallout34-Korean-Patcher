"""Find FNV+DLC original Korean strings lost when Fallout34 changed fields.

This is the conservative text-only analogue of the FO3 cross-field analysis:
the original, plugin-owned source record+field must be the *only* exact native
original occurrence of a >=40-character English line and the corresponding
exact source ESM/SST record must have unique Korean. Converted target bytes
are checked independently. These are contextual review candidates: without
the converter's source-FormID link they must NOT be treated as proven in-game
speaker/context identity. Game files and online mod stay untouched.
"""
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path

import recover_fo3_cross_field_text_provenance as common

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fnv"
SST = common.SST
SOURCE_DIR = Path(r"C:\Games\Steam\steamapps\common\Fallout New Vegas\Data")
TARGET = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data\FalloutNV34.esm")
PLUGINS = ("falloutnv", "deadmoney", "honesthearts", "oldworldblues",
           "lonesomeroad", "gunrunnersarsenal", "caravanpack",
           "classicpack", "mercenarypack", "tribalpack")
PLANS = common.ACTIVE_PLANS[:-1] + ("import_manifest_migrated_verified.jsonl.gz",)


def run():
    reader, fo3, native = common.modules()
    expected = json.loads((DATA / "indexed_plan_report.json").read_text("utf8"))["esm_sha256"]
    if fo3.hash_file(TARGET) != expected:
        raise RuntimeError("FNV converted ESM does not match pinned scan")
    known = {}
    for fname in PLANS:
        for r in common.load(DATA / fname):
            k = r["target_formid"], r["record_type"], r["field"], int(r["target_field_occurrence_index"])
            val = r["english"], r["korean"]
            if k in known and known[k] != val:
                raise RuntimeError(f"Inconsistent existing plan {k}")
            known[k] = val
    residual_by_text = defaultdict(list)
    for r in common.load(DATA / "xtranslator_residual_candidates.jsonl.gz"):
        k = r["formid"], r["record_type"], r["field"], int(r["index"])
        if k in known or r["priority"] != "P0" or r["conditional_proc"] is not None:
            continue
        if (r["record_type"], r["field"]) not in common.TARGET_FIELDS:
            continue
        if len(r["english"].strip()) < common.MIN_ENGLISH_LENGTH:
            continue
        if r["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        residual_by_text[r["english"]].append(r)
    original_occurrence = defaultdict(set)
    source_subindices = defaultdict(set)
    original_sha = {}
    for name in PLUGINS:
        path = SOURCE_DIR / (name + ".esm")
        plugin_name = name + ".esm"
        owner = native.original_owner_index(path)
        for fp, offset, size, flags, fid, typ in fo3.records(path):
            if typ.encode("ascii", "replace") not in common.SOURCE_TYPES or (fid >> 24) != owner:
                continue
            for field, idx, raw in fo3.fields(fo3.read_record(fp, offset, size, flags)):
                text = fo3.decode(raw)
                if text not in residual_by_text:
                    continue
                k = (plugin_name, fid & 0xFFFFFF, typ, field, text)
                original_occurrence[text].add(k[:4])
                source_subindices[k].add(idx)
        original_sha[plugin_name] = fo3.hash_file(path)

    exact_sst = defaultdict(set)
    sst_hashes = {}
    for name in PLUGINS:
        file = SST / (name + "_en_ko.sst")
        parsed = reader.parse_sst(file)
        sst_hashes[file.name] = parsed["sha256"]
        masters = [x.casefold() for x in parsed["master_files"]]
        for row in parsed["records"]:
            fid = int(row["form_id"], 16)
            if fid >> 24 >= len(masters):
                continue
            key = (masters[fid >> 24], fid & 0xFFFFFF,
                   row["record_name"], row["field_name"], row["source"])
            if key not in source_subindices or row["index"] not in source_subindices[key]:
                continue
            if row["korean"] and row["korean"] != row["source"]:
                exact_sst[key].add((row["korean"], file.name, int(row["index"])))
    verified = []
    review = []
    states = Counter()
    migrations = Counter()
    for english, rows in residual_by_text.items():
        origins = original_occurrence.get(english, set())
        if not origins:
            state = "absent_from_original_esm"
        elif len(origins) != 1:
            state = "ambiguous_multiple_original_records_or_fields"
        else:
            src_plugin, src_id, src_type, src_field = next(iter(origins))
            hits = exact_sst.get((src_plugin, src_id, src_type, src_field, english), set())
            korean_values = {ko for ko, _, _ in hits}
            if not hits:
                state = "source_field_has_no_exact_korean_sst"
            elif len(korean_values) != 1:
                state = "original_sst_conflicting_korean"
            else:
                korean = next(iter(korean_values))
                if not korean.strip() or "\ufffd" in korean or Counter(common.TOKEN.findall(english)) != Counter(common.TOKEN.findall(korean)):
                    state = "invalid_korean_formatting"
                else:
                    state = "unique_original_text_field_sst_verified"
        states[state] += len(rows)
        if state != "unique_original_text_field_sst_verified":
            review.append({
                "english": english, "fields": [
                    [r["formid"], r["record_type"], r["field"], int(r["index"])] for r in rows[:8]
                ], "count": len(rows), "status": state,
                "source_count": len(origins),
            })
            continue
        for row in rows:
            proof = {
                "plugin": src_plugin, "source_local_formid": f"{src_id:06X}",
                "source_record_type": src_type, "source_field": src_field,
                "source_sst": [{"file": file, "index": index} for ko, file, index in sorted(hits)],
                "match_type": "globally_unique_original_long_text_not_direct_formid_link",
            }
            verified.append({
                "target_formid": row["formid"], "record_type": row["record_type"],
                "field": row["field"], "target_field_occurrence_index": int(row["index"]),
                "english": english, "korean": korean,
                "previous_unlinked_class": row["status"],
                "plan_source": "fnv_unique_source_long_text_cross_field_candidate",
                "source_evidence": proof,
            })
            migrations[(src_type, src_field, row["record_type"], row["field"])] += 1
    # Independently re-read all target ESM fields, without relying on the
    # previous xTranslator residual data's byte values.
    by_id = defaultdict(list)
    for row in verified:
        by_id[int(row["target_formid"], 16)].append(row)
    seen, found = set(), set()
    for fid, typ, decoded in native.esm_records(TARGET, set(by_id)):
        if fid in seen:
            raise RuntimeError("Repeated target FormID")
        seen.add(fid)
        for row in by_id[fid]:
            key = row["target_formid"], row["record_type"], row["field"], row["target_field_occurrence_index"]
            if typ != row["record_type"] or decoded.get((row["field"], key[3])) != row["english"]:
                raise RuntimeError(f"Target ESM text differs at {key}")
            if key in found:
                raise RuntimeError("Duplicate target field")
            found.add(key)
    if len(found) != len(verified) or fo3.hash_file(TARGET) != expected:
        raise RuntimeError("Target changed or some fields absent")
    verified.sort(key=lambda r: (r["target_formid"],r["record_type"],r["field"],r["target_field_occurrence_index"]))
    common.save(DATA / "fnv_cross_field_long_text_verified.jsonl.gz", verified)
    common.save(DATA / "fnv_cross_field_long_text_review.jsonl.gz", review)
    report = {
        "game": "fnv",
        "target_esm_sha256": expected,
        "original_source_esm_hashes": original_sha,
        "source_sst_hashes": sst_hashes,
        "candidate_english_unique": len(residual_by_text),
        "candidate_field_occurrences": sum(map(len, residual_by_text.values())),
        "unique_source_text_sst_verified_fields": len(verified),
        "classification": dict(states),
        "source_to_target_field_migration": {
            f"{a}/{b} -> {c}/{d}": n
            for (a, b, c, d), n in migrations.most_common()
        },
        "warning": "High-confidence text-only original uniqueness evidence, not direct converter FormID provenance. Runtime context and dialogue QA remain needed. Only data outputs written.",
    }
    (DATA / "fnv_cross_field_long_text_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print("FNV VERIFIED",len(verified),"MIGRATIONS",migrations.most_common(15),
          "STATES",states,flush=True)


if __name__ == "__main__":
    run()
