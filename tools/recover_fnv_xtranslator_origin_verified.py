"""Find safe FNV xTranslator residual recovery from actual original ESMs and SST.

Inputs are read-only. Output candidates are independent of the live patch plan;
the integrator must merge them after reviewing the report. An assignment requires:
  - explicit converter source FormID or a generated-key original source FormID;
  - matching record type, field, and source text in the original game's ESM;
  - that exact source FormID/type/field/text in its Korean xTranslator SST;
  - identical target FormID/type/field/occurrence/text in pinned FalloutNV34.esm;
  - a single Korean translation and matching in-game formatting tokens.
No cross-game or English-only translation-memory fallback is allowed.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import csv
import gzip
import hashlib
import importlib.util
import json
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "fnv"
NV_DATA = Path(r"C:\Games\Steam\steamapps\common\Fallout New Vegas\Data")
FO4 = Path(r"C:\Games\Steam\steamapps\common\Fallout 4")
SST_DIR = Path("F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV")
SST_NAMES = ("falloutnv", "deadmoney", "honesthearts", "oldworldblues",
             "lonesomeroad", "gunrunnersarsenal", "caravanpack", "classicpack",
             "mercenarypack", "tribalpack")
ORIGIN_RE = re.compile(r"(?i)^([a-z0-9._ \-]+\.esm):([a-f0-9]{6})$")
EDIT_CUE = re.compile(r"^\s*(?:\{[^{}\r\n]{1,160}\}\s*)+")
TOKEN = re.compile(
    r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]"
    r"|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>"
    r"|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}"
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write_lines(path: Path, entries):
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as out:
        for item in entries:
            out.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def readable(raw: bytes):
    if not raw or len(raw) > 131072 or b"\0" in raw[:-1]:
        return None
    payload = raw.rstrip(b"\0")
    if not payload:
        return None
    for codec in ("utf-8", "cp1252"):
        try:
            value = payload.decode(codec)
        except UnicodeError:
            continue
        if all(c.isprintable() or c in "\r\n\t" for c in value):
            return value
    return None


def fields(payload: bytes):
    index = Counter()
    pos = 0
    extended = 0
    while pos + 6 <= len(payload):
        tag, length = struct.unpack_from("<4sH", payload, pos)
        pos += 6
        if tag == b"XXXX":
            if length != 4 or pos + 4 > len(payload):
                raise ValueError("invalid extended field size")
            extended = struct.unpack_from("<I", payload, pos)[0]
            pos += 4
            continue
        length = extended if extended else length
        extended = 0
        if pos + length > len(payload):
            raise ValueError("field exceeds record data")
        name = tag.decode("ascii", "replace")
        idx = index[name]
        index[name] += 1
        yield name, idx, payload[pos:pos + length]
        pos += length
    if pos != len(payload):
        raise ValueError("trailing malformed field data")


def esm_records(path: Path, selected_ids: set[int], *, owner_index: int | None = None):
    """Yield selected records, using the 24-byte FO3/FNV/FO4 record headers."""
    end = path.stat().st_size
    with path.open("rb") as stream:
        pos = 0
        while pos < end:
            stream.seek(pos)
            hdr = stream.read(24)
            if len(hdr) != 24:
                raise ValueError(f"truncated header at {pos} in {path}")
            tag, size, flags, fid, _, _ = struct.unpack("<4sIIIII", hdr)
            if tag == b"GRUP":
                if size < 24 or pos + size > end:
                    raise ValueError(f"invalid group at {pos} in {path}")
                pos += 24
                continue
            if size > 16 * 1024 * 1024 or pos + 24 + size > end:
                raise ValueError(f"invalid record at {pos} in {path}")
            # Original DLCs usually store their OWN records as 01xxxxxx:
            # 00xxxxxx belongs to FalloutNV.esm, their first MAST.
            selected = (fid & 0xFFFFFF) in selected_ids and (fid >> 24) == owner_index if owner_index is not None else fid in selected_ids
            if selected:
                payload = stream.read(size)
                if flags & 0x00040000:
                    if len(payload) < 4:
                        raise ValueError("short compressed record")
                    expanded_size = struct.unpack_from("<I", payload)[0]
                    payload = zlib.decompress(payload[4:])
                    if len(payload) != expanded_size:
                        raise ValueError("wrong decompressed record length")
                decoded = {(name, idx): readable(raw) for name, idx, raw in fields(payload)}
                yield fid & 0xFFFFFF if owner_index is not None else fid, tag.decode("ascii", "replace"), decoded
            pos += 24 + size
        if pos != end:
            raise ValueError(f"record traversal incomplete in {path}")


def original_owner_index(path: Path) -> int:
    with path.open("rb") as stream:
        h = stream.read(24)
        if len(h) != 24:
            raise ValueError(f"Invalid original ESM {path}")
        tag, size, _, _, _, _ = struct.unpack("<4sIIIII", h)
        if tag != b"TES4" or size > 1024 * 1024:
            raise ValueError(f"Missing original TES4 header {path}")
        data = stream.read(size)
    return sum(1 for name, _, _ in fields(data) if name == "MAST")


def dialogue_parents(path: Path, selected_info: set[int], owner_index: int):
    """Prove an INFO belongs to a specific parent DIAL via ESM GRUP type 7.

    Reads only the source game's original ESM. A parent must be an actual DIAL
    record from the same original plugin, not merely a coincident English line.
    """
    parents = {}
    dialogs = {}
    stack = []
    end = path.stat().st_size
    with path.open("rb") as stream:
        pos = 0
        while pos < end:
            while stack and pos >= stack[-1][0]:
                stack.pop()
            stream.seek(pos)
            hdr = stream.read(24)
            if len(hdr) != 24:
                raise ValueError(f"Truncated original dialogue header at {pos}")
            tag, size, flags, fid, _, _ = struct.unpack("<4sIIIII", hdr)
            if tag == b"GRUP":
                if size < 24 or pos + size > end:
                    raise ValueError(f"Invalid original dialogue group at {pos}")
                label, group_type = struct.unpack_from("<II", hdr, 8)
                stack.append((pos + size, group_type, label))
                pos += 24
                continue
            if size > 16 * 1024 * 1024 or pos + 24 + size > end:
                raise ValueError(f"Invalid original dialogue record at {pos}")
            if (fid >> 24) == owner_index:
                local = fid & 0xFFFFFF
                if tag == b"INFO" and local in selected_info:
                    dialog_group = next((x for x in reversed(stack) if x[1] == 7), None)
                    if dialog_group and (dialog_group[2] >> 24) == owner_index:
                        if local in parents and parents[local] != (dialog_group[2] & 0xFFFFFF):
                            raise ValueError(f"Original INFO has conflicting DIAL parents: {local:06X}")
                        parents[local] = dialog_group[2] & 0xFFFFFF
                elif tag == b"DIAL":
                    payload = stream.read(size)
                    if flags & 0x00040000:
                        expected = struct.unpack_from("<I", payload)[0]
                        payload = zlib.decompress(payload[4:])
                        if len(payload) != expected:
                            raise ValueError("Corrupt original DIAL compressed record")
                    full = {idx: readable(blob) for name, idx, blob in fields(payload)
                            if name == "FULL"}
                    if local in dialogs:
                        raise ValueError(f"Duplicate original DIAL ID {local:06X}")
                    dialogs[local] = full
            pos += 24 + size
    if pos != end:
        raise ValueError("Incomplete original dialogue group walk")
    return {info: (parent, dialogs[parent])
            for info, parent in parents.items() if parent in dialogs}


def origins_from_sst():
    spec = importlib.util.spec_from_file_location("fnv_sst_parser", ROOT / "tools" / "read_xtranslator_sst.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    # The SST native FormID is in the master's load order. Normalize to ESM plugin + 24-bit local ID.
    translated = defaultdict(set)
    per_sst = {}
    for part in SST_NAMES:
        path = SST_DIR / (part + "_en_ko.sst")
        parsed = reader.parse_sst(path)
        per_sst[path.name] = parsed["sha256"]
        masters = [x.casefold() for x in parsed["master_files"]]
        for r in parsed["records"]:
            fid = int(r["form_id"], 16)
            if (fid >> 24) >= len(masters):
                continue
            plugin = masters[fid >> 24]
            if not plugin.endswith(".esm") or not r["korean"] or r["source"] == r["korean"]:
                continue
            key = (plugin, fid & 0xFFFFFF, r["record_name"], r["field_name"], r["source"])
            translated[key].add((r["korean"], path.name, int(r["index"])))
    return translated, per_sst


def main():
    target = FO4 / "Data" / "FalloutNV34.esm"
    if not target.is_file():
        target = FO4 / "Fallout34_Work" / "fnv" / "staging" / "Data" / "FalloutNV34.esm"
    pin = json.loads((DATA / "indexed_plan_report.json").read_text(encoding="utf-8"))["esm_sha256"]
    if digest(target) != pin:
        raise RuntimeError("The target FalloutNV34.esm differs from the recorded SHA256; regenerate residual scan.")

    residual = {}
    for r in lines(DATA / "xtranslator_residual_candidates.jsonl.gz"):
        if r["status"] not in ("missing_translation_match", "existing_korean_needs_context"):
            continue
        key = (r["formid"], r["record_type"], r["field"], int(r["index"]))
        if key in residual:
            raise RuntimeError(f"Duplicate residual key {key}")
        residual[key] = r
    missing_by_id = defaultdict(list)
    for key, item in residual.items():
        missing_by_id[key[0]].append(item)

    known = {}
    for name in ("indexed_patch_plan_candidates.jsonl.gz", "indexed_patch_plan_v2_strict_extra.jsonl.gz"):
        for r in lines(DATA / name):
            key = (r["target_formid"].replace("0x", "").upper(), r["record_type"],
                   r["field"], int(r["target_field_occurrence_index"]))
            if key in known and (known[key]["english"], known[key]["korean"]) != (r["english"], r["korean"]):
                raise RuntimeError(f"Conflicting existing plan at {key}")
            known[key] = r

    origin_links = defaultdict(set)
    evidence = defaultdict(lambda: defaultdict(set))
    with gzip.open(DATA / "converter_formid_map.tsv.gz", "rt", encoding="utf-8", newline="") as stream:
        for r in csv.DictReader(stream, delimiter="\t"):
            fid = r["formid"].upper()
            if fid not in missing_by_id:
                continue
            m = ORIGIN_RE.fullmatch(r["source"])
            if not m:
                continue
            src = (m[1].casefold(), int(m[2], 16))
            origin_links[fid].add(src)
            evidence[fid][src].add("converter_formid_map")
    with gzip.open(DATA / "converter_origin_keys_selected.tsv.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            vals = line.rstrip("\r\n").split("\t", 3)
            if len(vals) != 4 or vals[0] not in missing_by_id:
                continue
            fid, rec_type, _, key = vals
            if not any(r["record_type"] == rec_type for r in missing_by_id[fid]):
                continue
            for segment in key.split("|"):
                m = ORIGIN_RE.fullmatch(segment)
                if not m:
                    continue
                src = (m[1].casefold(), int(m[2], 16))
                origin_links[fid].add(src)
                evidence[fid][src].add("converter_generated_key")
                if rec_type == "INFO" and key.startswith("INFO|dlg|"):
                    evidence[fid][src].add("converter_dialogue_key")

    sst_rows, sst_hashes = origins_from_sst()
    # The converter preserves the source's low 24-bit FormID for base-game
    # records in the first master range. Its map TSV records remapped IDs but
    # omits many identity IDs. Only infer the canonical 01 + 00xxxxxx range,
    # and still require original ESM + exact SST record/type/field/text proof.
    implicit_base_origins = 0
    for fid in missing_by_id:
        value = int(fid, 16)
        if not (0x01000000 <= value < 0x01100000):
            continue
        if origin_links.get(fid):
            continue
        source = ("falloutnv.esm", value & 0xFFFFFF)
        origin_links[fid].add(source)
        evidence[fid][source].add("base_game_identity_formid_with_source_esm_proof")
        implicit_base_origins += 1
    original_ids = defaultdict(set)
    translatable_origin_ids = {(plugin, fid) for plugin, fid, _, _, _ in sst_rows}
    for fid, origins in origin_links.items():
        for plugin, local in origins:
            if (plugin, local) in translatable_origin_ids:
                original_ids[plugin].add(local)
    # Only inspect source plugin records to which the SST dictionary can refer.
    original = {}
    source_hashes = {}
    for plugin, ids in original_ids.items():
        path = NV_DATA / plugin
        if not path.is_file():
            continue
        seen = set()
        for source_id, typ, raw_fields in esm_records(path, ids, owner_index=original_owner_index(path)):
            k = (plugin, source_id & 0xFFFFFF)
            if k in seen:
                raise RuntimeError(f"Duplicate original record {k}")
            seen.add(k)
            original[k] = (typ, raw_fields)
        source_hashes[plugin] = digest(path)

    dialogue_ids = defaultdict(set)
    for target_fid, rows in missing_by_id.items():
        if not any(r["record_type"] == "INFO" and r["field"] == "RNAM" for r in rows):
            continue
        for source in origin_links.get(target_fid, ()):
            if "converter_dialogue_key" in evidence[target_fid][source]:
                dialogue_ids[source[0]].add(source[1])
    original_dialogue_parent = {}
    for plugin, ids in dialogue_ids.items():
        path = NV_DATA / plugin
        if not path.is_file():
            continue
        parent_map = dialogue_parents(path, ids, original_owner_index(path))
        for info_id, (dial_id, fields_by_index) in parent_map.items():
            original_dialogue_parent[(plugin, info_id)] = ((plugin, dial_id), fields_by_index)
        if plugin not in source_hashes:
            source_hashes[plugin] = digest(path)

    stats = Counter()
    by_field = defaultdict(Counter)
    by_input_status = defaultdict(Counter)
    failure_by_field = defaultdict(Counter)
    examples = defaultdict(list)
    candidates = []
    reviews = []
    for key, row in residual.items():
        fid, target_type, field, idx = key
        english = row["english"]
        origins = sorted(origin_links.get(fid, set()))
        matches = defaultdict(set)
        failures = Counter()
        source_evidence = []
        for source in origins:
            # The source INFO's DIAL-group parent is the exact player
            # dialogue prompt from which a generated INFO/RNAM option arose.
            if (target_type, field) == ("INFO", "RNAM") and (
                    "converter_dialogue_key" in evidence[fid][source]):
                parent = original_dialogue_parent.get(source)
                if parent:
                    parent_source, parent_fields = parent
                    for original_full in parent_fields.values():
                        if original_full is None:
                            continue
                        if original_full == english:
                            transform = "original_info_parent_dial_full"
                        elif EDIT_CUE.match(original_full) and (
                                EDIT_CUE.sub("", original_full).strip() == english):
                            transform = "original_info_parent_dial_full_editor_cue_removed"
                        else:
                            continue
                        source_key = (*parent_source, "DIAL", "FULL", original_full)
                        for korean, sst_name, sst_idx in sst_rows.get(source_key, set()):
                            if not korean or korean == english:
                                failures["dialogue_parent_same_text_or_empty"] += 1
                            elif Counter(TOKEN.findall(english)) != Counter(TOKEN.findall(korean)):
                                failures["dialogue_parent_placeholder_mismatch"] += 1
                            elif korean.startswith("{") and transform.endswith("editor_cue_removed"):
                                failures["dialogue_parent_translation_contains_cue"] += 1
                            else:
                                matches[korean].add((source, sst_name, sst_idx, transform, parent_source))
                else:
                    failures["dialogue_parent_missing"] += 1
            source_row = original.get(source)
            if source_row is None:
                failures["original_esm_record_unavailable"] += 1
                continue
            record_type, source_fields = source_row
            if (target_type, field) == ("INFO", "RNAM") and record_type == "DIAL" and (
                    "converter_dialogue_key" in evidence[fid][source]):
                for (name, _), original_full in source_fields.items():
                    if name != "FULL" or original_full is None:
                        continue
                    if original_full == english:
                        transform = "generated_info_from_source_dial_full"
                    elif EDIT_CUE.match(original_full) and EDIT_CUE.sub("", original_full).strip() == english:
                        transform = "generated_info_from_source_dial_full_editor_cue_removed"
                    else:
                        continue
                    source_key = (*source, "DIAL", "FULL", original_full)
                    for korean, sst_name, sst_idx in sst_rows.get(source_key, set()):
                        if not korean or korean == english:
                            failures["direct_dial_same_text_or_empty"] += 1
                        elif Counter(TOKEN.findall(english)) != Counter(TOKEN.findall(korean)):
                            failures["direct_dial_placeholder_mismatch"] += 1
                        elif korean.startswith("{") and transform.endswith("editor_cue_removed"):
                            failures["direct_dial_translation_contains_cue"] += 1
                        else:
                            matches[korean].add((source, sst_name, sst_idx, transform, source))
            if record_type != target_type:
                failures["original_record_type_different"] += 1
                continue
            same_field = [value for (tag, _), value in source_fields.items() if tag == field]
            if english in same_field:
                source_texts = [english]
                transform = "exact_source_text"
            else:
                source_texts = [value for value in same_field if value is not None
                                and EDIT_CUE.match(value)
                                and EDIT_CUE.sub("", value).strip() == english]
                transform = "converter_removed_leading_editor_cue"
            if not source_texts:
                failures["source_esm_field_english_not_matching"] += 1
                continue
            for source_english in source_texts:
                sst_key = (*source, target_type, field, source_english)
                sst_found = sst_rows.get(sst_key, set())
                if not sst_found:
                    failures["same_original_source_field_not_translated_in_sst"] += 1
                for korean, sst_name, sst_idx in sst_found:
                    if not korean or korean == english:
                        failures["same_text_or_empty"] += 1
                    elif Counter(TOKEN.findall(english)) != Counter(TOKEN.findall(korean)):
                        failures["placeholder_mismatch"] += 1
                    elif korean.startswith("{") and transform == "converter_removed_leading_editor_cue":
                        failures["translated_text_still_has_editor_cue"] += 1
                    else:
                        matches[korean].add((source, sst_name, sst_idx, transform, None))
        if not origins:
            status = "no_converter_origin"
        elif not matches:
            status = "no_proven_source_field_translation"
        elif len(matches) != 1:
            status = "different_korean_for_same_target"
        else:
            status = "source_esm_sst_field_verified"
        stats[status] += 1
        by_input_status[row["status"]][status] += 1
        signature = target_type + "/" + field
        by_field[signature][status] += 1
        if status != "source_esm_sst_field_verified":
            failure_by_field[signature].update(failures)
        if len(examples[status]) < 5:
            examples[status].append({"id": fid, "field": signature, "english": english[:140],
                                     "origin_count": len(origins), "failures": dict(failures)})
        output = {
            "target_formid": fid, "record_type": target_type, "field": field,
            "target_field_occurrence_index": idx, "english": english,
            "origin_verification_status": status,
            "xtranslator_input_status": row["status"],
        }
        if status == "source_esm_sst_field_verified":
            korean, proven = next(iter(matches.items()))
            output["korean"] = korean
            output["plan_source"] = "fnv_xtranslator_origin_esm_sst_verified"
            output["source_evidence"] = [
                {"plugin": source[0], "original_local_formid": f"{source[1]:06X}",
                 "source_sst": sst_file, "source_sst_field_index": sst_idx,
                 "source_sst_record_type": ("DIAL" if parent else target_type),
                 "source_sst_field": ("FULL" if parent else field),
                 "transform": transform, "origin_link": sorted(evidence[fid][source]),
                 "dialogue_parent_formid": (f"{parent[1]:06X}" if parent else None)}
                for source, sst_file, sst_idx, transform, parent in sorted(proven)
            ]
            candidates.append(output)
        else:
            output["suggested_korean"] = sorted(matches.keys())[:3]
            output["origin_links"] = [f"{p}:{sid:06x}" for p, sid in origins[:12]]
            output["failure_counts"] = dict(failures)
            reviews.append(output)

    # Independent read of the exact target field bytes. Fail closed if any row fails.
    by_target = defaultdict(list)
    for row in candidates:
        by_target[int(row["target_formid"], 16)].append(row)
    verified = []
    verified_status = Counter()
    seen_ids = set()
    for fid, typ, raw_fields in esm_records(target, set(by_target)):
        if fid in seen_ids:
            raise RuntimeError(f"Duplicate target record FormID {fid:08X}")
        seen_ids.add(fid)
        for row in by_target[fid]:
            key = (row["field"], row["target_field_occurrence_index"])
            if typ != row["record_type"]:
                reason = "target_record_type_changed"
            elif raw_fields.get(key) != row["english"]:
                reason = "target_field_english_changed"
            else:
                reason = "target_byte_verified"
            verified_status[reason] += 1
            if reason == "target_byte_verified":
                verified.append(row)
            else:
                row["origin_verification_status"] = reason
                reviews.append(row)
    for fid in set(by_target) - seen_ids:
        for row in by_target[fid]:
            row["origin_verification_status"] = "target_formid_missing"
            reviews.append(row)
            verified_status["target_formid_missing"] += 1
    if digest(target) != pin:
        raise RuntimeError("ESM changed during verification, no output saved")

    # Existing-plan keys and residual keys must be disjoint; make this an invariant.
    collisions = [
        (r["target_formid"], r["record_type"], r["field"], r["target_field_occurrence_index"])
        for r in verified
        if (r["target_formid"], r["record_type"], r["field"], r["target_field_occurrence_index"]) in known
    ]
    if collisions:
        raise RuntimeError(f"New candidates overlap current plan, first collision: {collisions[0]}")
    verified.sort(key=lambda r: (r["target_formid"], r["record_type"], r["field"],
                                 r["target_field_occurrence_index"]))
    write_lines(DATA / "xtranslator_fallback_source_verified.jsonl.gz", verified)
    write_lines(DATA / "xtranslator_fallback_source_review.jsonl.gz", reviews)
    report = {
        "game": "fnv", "source_target_esm": str(target), "target_esm_sha256": pin,
        "source_original_esm_sha256": source_hashes, "sst_sha256": sst_hashes,
        "residual_occurrences_checked": len(residual),
        "source_origins_in_converter": sum(bool(v) for v in origin_links.values()),
        "implicit_base_origin_ids_considered": implicit_base_origins,
        "original_source_records_loaded": len(original),
        "source_info_to_parent_dialogue_links": len(original_dialogue_parent),
        "classification": dict(stats), "by_record_field": {k: dict(v) for k, v in sorted(by_field.items())},
        "by_xtranslator_input_status": {k: dict(v) for k, v in by_input_status.items()},
        "unresolved_source_failures_by_field": {k: dict(v) for k, v in sorted(failure_by_field.items())},
        "target_byte_verification": dict(verified_status),
        "verified_new_candidate_occurrences": len(verified),
        "manual_review_occurrences": len(reviews), "samples": dict(examples),
        "warning": "Includes xTranslator missing and existing-Korean-needs-context entries. Read-only original game ESM and SST provenance check. This writes assignments for later integration, no ESP/STRINGS, no runtime reachability verification. Conditional xTranslator proc and binary record fields need runtime checks.",
    }
    (DATA / "xtranslator_fallback_source_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("FNV", json.dumps({k: v for k, v in report.items()
                             if k not in ("by_record_field", "unresolved_source_failures_by_field", "samples", "source_original_esm_sha256",
                                          "sst_sha256", "source_target_esm", "warning")},
                            ensure_ascii=True), flush=True)
    print("TOP_FNV_FIELDS", sorted(
        ((k, v["source_esm_sst_field_verified"]) for k, v in by_field.items()
         if v["source_esm_sst_field_verified"]), key=lambda x: -x[1])[:20], flush=True)


if __name__ == "__main__":
    main()
