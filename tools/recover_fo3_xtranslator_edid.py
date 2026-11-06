"""Recover remaining FO3+DLC xTranslator gaps by exact ORIGINAL EDID identity.

Fallback for converter-assigned FormIDs that differ from the original ESM IDs.
Only uniquely matching source-owner record EDIDs, same record type, field slot,
English text, and indexed SST translation qualify. Never modifies game files.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import gzip
import importlib.util
import json
from pathlib import Path

import recover_fo3_xtranslator_provenance as core

ROOT, DATA = core.ROOT, core.DATA


def converted_edid_source_key(edid):
    # Verified on an unchanged direct-ID TERM: source
    # genericProtectronTerminalDesk -> F3_genericProtectronTerminalDesk.
    # This is merely a lookup hypothesis; source record, field index and SST
    # still need to match before accepting any translated assignment.
    return edid[3:].casefold() if edid.startswith("F3_") else edid.casefold()


def load(name):
    with gzip.open(DATA / name, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def main():
    previous = json.loads((DATA / "xtranslator_fo3_provenance_report.json").read_text(encoding="utf-8"))
    expected = previous["converted_esm_sha256"]
    if core.hash_file(core.TARGET) != expected:
        raise RuntimeError("Converted ESM changed: abort")
    already = set()
    for name in ("indexed_patch_plan_candidates.jsonl.gz", "indexed_patch_plan_v2_strict_extra.jsonl.gz", "xtranslator_fo3_provenance_exact.jsonl.gz"):
        for r in load(name):
            already.add((r["target_formid"], r["record_type"], r["field"], int(r["target_field_occurrence_index"])))
    remaining_by_id = defaultdict(list)
    for r in load("xtranslator_residual_candidates.jsonl.gz"):
        if r["status"] != "missing_translation_match" or r["field"] not in core.DISPLAY_FIELDS.get(r["record_type"], set()) or r.get("conditional_proc"):
            continue
        target_key = (r["formid"], r["record_type"], r["field"], int(r["index"]))
        if target_key in already:
            continue
        remaining_by_id[int(r["formid"], 16)].append(r)

    stats = Counter()
    review = []
    id_by_edid = defaultdict(list)
    target_edids = set()
    # Detect an EDID from the same physical record and verify target English again.
    for f, at, size, flags, fid, typ in core.records(core.TARGET):
        if fid not in remaining_by_id:
            continue
        raw_fields = list(core.fields(core.read_record(f, at, size, flags)))
        edids = [core.decode(b) for field, idx, b in raw_fields if field == "EDID"]
        edid = edids[0] if len(edids) == 1 else None
        strings = {(field, idx): core.decode(b) for field, idx, b in raw_fields}
        for r in remaining_by_id.pop(fid):
            if not edid or typ != r["record_type"] or strings.get((r["field"], r["index"])) != r["english"]:
                stats["target_edid_missing_or_field_changed"] += 1
                review.append({**r, "review_reason": "target_edid_missing_or_field_changed"})
                continue
            key = (typ, converted_edid_source_key(edid))
            id_by_edid[key].append((r, edid))
            target_edids.add(key)
    for lost in remaining_by_id.values():
        for r in lost:
            review.append({**r, "review_reason": "target_record_missing"})
            stats["target_record_missing"] += 1

    # Original owner + type + exact EDID. Master-owned overrides don't provide
    # reliable provenance for DLC-generated IDs and are excluded.
    original = defaultdict(list)
    original_counts = {}
    for plugin in core.PLUGIN_OFFSETS:
        file = core.FO3_DATA / core.PLUGIN_NAMES[plugin]
        if core.hash_file(file) != previous["source_esm_sha256"][plugin]:
            raise RuntimeError(f"Original ESM changed: {file}")
        owner = None
        total = 0
        for f, at, size, flags, fid, typ in core.records(file):
            if typ == "TES4" and owner is None:
                owner = sum(field == "MAST" for field, _, _ in core.fields(core.read_record(f, at, size, flags)))
                continue
            if fid >> 24 != owner:
                continue
            values = list(core.fields(core.read_record(f, at, size, flags)))
            edid_vals = [core.decode(b) for field, _, b in values if field == "EDID"]
            if len(edid_vals) != 1 or not edid_vals[0]:
                continue
            key = (typ, edid_vals[0].casefold())
            if key not in target_edids:
                continue
            texts = {(field, idx): core.decode(b) for field, idx, b in values}
            original[key].append((plugin, fid, texts, edid_vals[0]))
            total += 1
        original_counts[plugin] = total

    # Load SST by its own recorded master list, preserving the original source ID.
    spec = importlib.util.spec_from_file_location("reader", ROOT / "tools" / "read_xtranslator_sst.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    selected_sources = {(plugin, fid & 0xFFFFFF) for sources in original.values() for plugin, fid, _, _ in sources}
    translations = defaultdict(set)
    sst_indices = defaultdict(set)
    for plugin in core.PLUGIN_OFFSETS:
        source = core.SST_DIR / (plugin.removesuffix(".esm") + "_en_ko.sst")
        parsed = reader.parse_sst(source)
        if parsed["sha256"] != previous["source_sst_sha256"][plugin]:
            raise RuntimeError(f"SST changed: {source}")
        masters = [m.casefold() for m in parsed["master_files"]]
        for row in parsed["records"]:
            fid = int(row["form_id"], 16)
            if fid >> 24 >= len(masters):
                continue
            owner_plugin = masters[fid >> 24]
            local = fid & 0xFFFFFF
            if (owner_plugin, local) not in selected_sources or not row["korean"] or row["source"] == row["korean"]:
                continue
            key = (owner_plugin, local, row["record_name"], row["field_name"], row["source"])
            translations[key].add(row["korean"])
            sst_indices[key].add(row["index"])

    passed = []
    by_field = defaultdict(Counter)
    for key, values in id_by_edid.items():
        sources = original.get(key, [])
        for r, target_edid in values:
            if len(sources) != 1:
                reason = "no_unique_original_owner_edid"
            else:
                plugin, fid, strings, source_edid = sources[0]
                index = int(r["index"])
                if strings.get((r["field"], index)) != r["english"]:
                    reason = "original_edid_field_index_english_mismatch"
                else:
                    lookup = (plugin, fid & 0xFFFFFF, r["record_type"], r["field"], r["english"])
                    ko_set = translations.get(lookup, set())
                    if len(ko_set) != 1:
                        reason = "sst_missing_or_korean_conflict"
                    elif index not in sst_indices[lookup]:
                        reason = "sst_index_mismatch"
                    else:
                        ko = next(iter(ko_set))
                        if ko == r["english"] or "\ufffd" in ko or Counter(core.TOKEN.findall(r["english"])) != Counter(core.TOKEN.findall(ko)):
                            reason = "translation_placeholder_invalid"
                        else:
                            passed.append({
                                "target_formid": r["formid"], "record_type": r["record_type"],
                                "field": r["field"], "target_field_occurrence_index": index,
                                "english": r["english"], "korean": ko,
                                "source_plugin": plugin, "source_formid": f"{fid:08X}",
                                "source_local_id": f"{fid & 0xFFFFFF:06X}",
                                "source_edid": source_edid, "target_edid": target_edid,
                                "source_field_index": index, "sst_field_index": index,
                                "priority": r["priority"], "plan_source": "xtranslator_fo3_original_owner_edid_field_index",
                            })
                            stats["exact_recovered"] += 1
                            by_field[r["record_type"] + "/" + r["field"]]["exact_recovered"] += 1
                            continue
            review.append({**r, "edid": target_edid, "review_reason": reason})
            stats[reason] += 1
            by_field[r["record_type"] + "/" + r["field"]][reason] += 1
    if core.hash_file(core.TARGET) != expected:
        raise RuntimeError("Converted ESM changed during scan")
    new_keys = [(r["target_formid"], r["record_type"], r["field"], r["target_field_occurrence_index"]) for r in passed]
    if len(new_keys) != len(set(new_keys)) or any(k in already for k in new_keys):
        raise RuntimeError("Recovered target collision")
    with gzip.open(DATA / "xtranslator_fo3_edid_exact.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in sorted(passed, key=lambda r: (r["target_formid"], r["record_type"], r["field"], r["target_field_occurrence_index"])):
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    with gzip.open(DATA / "xtranslator_fo3_edid_review.jsonl.gz", "wt", encoding="utf-8") as f:
        for row in review:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    report = {
        "game": "fo3", "converted_esm_sha256": expected,
        "candidate_target_edids": len(target_edids),
        "original_owner_edid_matches_by_plugin": original_counts,
        "exact_recovered": len(passed), "review_count": len(review),
        "reason_counts": dict(stats),
        "by_field": {key: dict(value) for key, value in by_field.items()},
        "examples": [{"target": r["target_formid"], "edid": r["target_edid"], "field": r["field"], "english": r["english"][:85]} for r in passed[:20]],
        "caveat": "Unique exact EDID in a source-owner ESM record is a static provenance link, not a runtime display guarantee. No ESP applied.",
    }
    (DATA / "xtranslator_fo3_edid_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"targets": len(target_edids), "original_matches": original_counts, "recovered": len(passed), "reasons": stats.most_common(12)}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
