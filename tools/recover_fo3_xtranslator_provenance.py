"""Recover FO3+DLC xTranslator gaps only with original-record/SST provenance.

Read-only game assets. Writes an independent patch-plan candidate and QA reports,
never an ESP and never changes the existing indexed plans. A converted record is
eligible only if the mapped original owner record, subrecord index, English, and
the original SST entry all match exactly.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "fo3"
FO3_DATA = Path(r"C:\Games\Steam\steamapps\common\Fallout 3 goty\Data")
TARGET = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm")
SST_DIR = Path("F:/번역/프로그램/xTranslator/UserDictionaries/FalloutNV")
PLUGIN_OFFSETS = {
    "fallout3.esm": 0x01000000,
    "anchorage.esm": 0x01100000,
    "thepitt.esm": 0x01140000,
    "brokensteel.esm": 0x01180000,
    "pointlookout.esm": 0x011C0000,
    "zeta.esm": 0x01200000,
}
PLUGIN_NAMES = {x.lower(): x for x in ("Fallout3.esm", "Anchorage.esm", "ThePitt.esm", "BrokenSteel.esm", "PointLookout.esm", "Zeta.esm")}
DISPLAY_FIELDS = {
    "INFO": {"RNAM", "NAM1"}, "DIAL": {"FULL"},
    "TERM": {"FULL", "UNAM", "ITXT", "BTXT"},
    "NOTE": {"FULL", "TNAM", "DESC"}, "MESG": {"FULL", "DESC", "ITXT", "DNAM"},
    "QUST": {"FULL", "CNAM"}, "LSCR": {"DESC"},
    "BOOK": {"FULL", "DESC", "CNAM"}, "NPC_": {"FULL"},
    "ARMO": {"FULL", "DESC"}, "WEAP": {"FULL", "DESC"},
    "AMMO": {"FULL"}, "MISC": {"FULL", "DESC"},
    "ALCH": {"FULL", "DESC"}, "INGR": {"FULL"},
    "CONT": {"FULL"}, "KEYM": {"FULL"}, "ACTI": {"FULL"},
    "DOOR": {"FULL"}, "FURN": {"FULL"}, "CELL": {"FULL"},
    "WRLD": {"FULL"}, "PERK": {"FULL", "DESC"},
    "SPEL": {"FULL", "DESC"}, "MGEF": {"FULL", "DNAM"},
    "FACT": {"FULL"}, "OMOD": {"FULL", "DESC"},
}
TOKEN = re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}")


def records(path):
    with path.open("rb") as f:
        total = path.stat().st_size
        pos = 0
        while pos < total:
            f.seek(pos)
            header = f.read(24)
            if len(header) != 24:
                raise ValueError(f"Truncated header in {path} at {pos}")
            typ, size, flags, fid, _, _ = struct.unpack("<4sIIIII", header)
            if typ == b"GRUP":
                if size < 24 or pos + size > total:
                    raise ValueError(f"Invalid GRUP in {path} at {pos}")
                pos += 24
                continue
            if size > 16 * 1024 * 1024 or pos + 24 + size > total:
                raise ValueError(f"Invalid record in {path} at {pos}")
            yield f, pos + 24, size, flags, fid, typ.decode("ascii", "replace")
            pos += size + 24


def fields(buf):
    pos = 0
    extended = 0
    indices = Counter()
    while pos + 6 <= len(buf):
        tag, n = struct.unpack_from("<4sH", buf, pos)
        pos += 6
        if tag == b"XXXX":
            if n != 4 or pos + 4 > len(buf):
                raise ValueError("Invalid XXXX")
            extended = struct.unpack_from("<I", buf, pos)[0]
            pos += 4
            continue
        n = extended or n
        extended = 0
        if pos + n > len(buf):
            raise ValueError("Truncated subrecord")
        name = tag.decode("ascii", "replace")
        index = indices[name]
        indices[name] += 1
        yield name, index, buf[pos:pos + n]
        pos += n


def read_record(f, at, size, flags):
    f.seek(at)
    blob = f.read(size)
    if flags & 0x00040000:
        if len(blob) < 4:
            raise ValueError("Bad compressed record")
        expected = struct.unpack_from("<I", blob)[0]
        blob = zlib.decompress(blob[4:])
        if len(blob) != expected:
            raise ValueError("Zlib size mismatch")
    return blob


def decode(blob):
    if not blob or len(blob) > 131072 or b"\0" in blob[:-1]:
        return None
    raw = blob.rstrip(b"\0")
    for encoding in ("utf-8", "cp1252"):
        try:
            s = raw.decode(encoding)
            if s and all(c.isprintable() or c in "\r\n\t" for c in s):
                return s
        except UnicodeDecodeError:
            continue
    return None


def hash_file(path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def load_rows(name):
    with gzip.open(DATA / name, "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def origin_for(fid):
    for plugin, offset in PLUGIN_OFFSETS.items():
        limit = 0x100000 if plugin == "fallout3.esm" else 0x40000
        if offset <= fid < offset + limit:
            return plugin, fid - offset
    return None


def run():
    expected = json.loads((DATA / "indexed_plan_report.json").read_text(encoding="utf-8"))["esm_sha256"]
    if hash_file(TARGET) != expected:
        raise RuntimeError("Converted ESM no longer matches indexed plan; aborting")
    already = {}
    for file in ("indexed_patch_plan_candidates.jsonl.gz", "indexed_patch_plan_v2_strict_extra.jsonl.gz"):
        for r in load_rows(file):
            key = (int(r["target_formid"], 16), r["record_type"], r["field"], int(r["target_field_occurrence_index"]))
            existing = (r["english"], r["korean"])
            if key in already and already[key] != existing:
                raise ValueError(f"Conflicting existing plan {key}")
            already[key] = existing

    targets = {}
    wanted = defaultdict(set)
    stats = Counter()
    by_field = defaultdict(Counter)
    def mark(row, reason):
        stats[reason] += 1
        by_field[row["record_type"] + "/" + row["field"]][reason] += 1
        return {**row, "review_reason": reason}

    review = []
    for r in load_rows("xtranslator_residual_candidates.jsonl.gz"):
        if r["status"] != "missing_translation_match":
            continue
        fid = int(r["formid"], 16)
        key = (fid, r["record_type"], r["field"], r["index"])
        if key in targets:
            raise ValueError(f"Duplicate extracted target {key}")
        origin = origin_for(fid)
        if not origin:
            review.append(mark(r, "not_in_known_fo3_dlc_id_range"))
            continue
        if r["field"] not in DISPLAY_FIELDS.get(r["record_type"], set()) or r.get("conditional_proc"):
            review.append(mark(r, "not_confirmed_display_field"))
            continue
        if key in already:
            review.append(mark(r, "already_covered_in_updated_plan"))
            continue
        targets[key] = (r, origin)
        wanted[origin[0]].add(origin[1])

    spec = importlib.util.spec_from_file_location("sst_reader", ROOT / "tools" / "read_xtranslator_sst.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    sst = defaultdict(set)
    sst_indexes = defaultdict(set)
    sst_sha = {}
    for plugin in PLUGIN_OFFSETS:
        path = SST_DIR / (plugin.removesuffix(".esm") + "_en_ko.sst")
        parsed = reader.parse_sst(path)
        sst_sha[plugin] = parsed["sha256"]
        masters = [name.casefold() for name in parsed["master_files"]]
        for row in parsed["records"]:
            form = int(row["form_id"], 16)
            if form >> 24 >= len(masters):
                continue
            owner = masters[form >> 24]
            if owner not in wanted or (form & 0xFFFFFF) not in wanted[owner]:
                continue
            if not row["korean"] or row["korean"] == row["source"]:
                continue
            key = (owner, form & 0xFFFFFF, row["record_name"], row["field_name"], row["source"])
            sst[key].add(row["korean"])
            sst_indexes[key].add(row["index"])

    # A source file may override a master-owned record. Accept only records that
    # belong to this plugin itself, as determined by its TES4 MAST list.
    sources = {}
    source_sha = {}
    owner_counts = {}
    for plugin in PLUGIN_OFFSETS:
        path = FO3_DATA / PLUGIN_NAMES[plugin]
        own_records = defaultdict(list)
        owner_index = None
        for f, at, size, flags, fid, typ in records(path):
            if typ == "TES4" and owner_index is None:
                header_fields = list(fields(read_record(f, at, size, flags)))
                owner_index = sum(name == "MAST" for name, _, _ in header_fields)
                continue
            if fid & 0xFFFFFF not in wanted[plugin]:
                continue
            if owner_index is None:
                raise ValueError(f"Missing TES4 header for {path}")
            if (fid >> 24) != owner_index:
                continue
            values = {(name, idx): decode(part) for name, idx, part in fields(read_record(f, at, size, flags))}
            own_records[fid & 0xFFFFFF].append((typ, values, f"{fid:08X}"))
        sources[plugin] = own_records
        owner_counts[plugin] = owner_index
        source_sha[plugin] = hash_file(path)

    # Re-read the converted ESM instead of trusting a prior extraction report.
    target_by_id = defaultdict(list)
    for key in targets:
        target_by_id[key[0]].append(key)
    checked = set()
    recovered = []
    for f, at, size, flags, fid, typ in records(TARGET):
        if fid not in target_by_id:
            continue
        values = {(name, idx): decode(part) for name, idx, part in fields(read_record(f, at, size, flags))}
        for key in target_by_id[fid]:
            if key in checked:
                review.append(mark(targets[key][0], "duplicate_target_formid"))
                continue
            checked.add(key)
            row, (plugin, local) = targets[key]
            field_index = (row["field"], int(row["index"]))
            if typ != row["record_type"] or values.get(field_index) != row["english"]:
                review.append(mark(row, "target_record_field_or_english_changed"))
                continue
            orig = sources[plugin].get(local, [])
            if len(orig) != 1:
                review.append(mark(row, "original_owner_record_missing_or_ambiguous"))
                continue
            source_type, source_fields, source_formid = orig[0]
            if source_type != typ or source_fields.get(field_index) != row["english"]:
                review.append(mark(row, "original_same_id_type_index_english_mismatch"))
                continue
            sst_key = (plugin, local, typ, row["field"], row["english"])
            ko_set = sst.get(sst_key, set())
            if len(ko_set) != 1:
                review.append(mark(row, "source_sst_missing_or_ko_conflict"))
                continue
            if int(row["index"]) not in sst_indexes[sst_key]:
                review.append(mark(row, "sst_field_index_mismatch"))
                continue
            ko = next(iter(ko_set))
            if "\ufffd" in ko or Counter(TOKEN.findall(row["english"])) != Counter(TOKEN.findall(ko)):
                review.append(mark(row, "korean_text_or_placeholder_invalid"))
                continue
            if ko == row["english"] or not ko.strip():
                review.append(mark(row, "korean_not_translated"))
                continue
            new = {
                "target_formid": row["formid"], "record_type": typ,
                "field": row["field"], "target_field_occurrence_index": row["index"],
                "english": row["english"], "korean": ko,
                "plan_source": "xtranslator_fo3_exact_original_owner_sst_index",
                "source_plugin": plugin, "source_formid": source_formid,
                "source_local_id": f"{local:06X}", "source_field_index": row["index"],
                "sst_field_index": row["index"], "priority": row["priority"],
            }
            recovered.append(new)
            stats["exact_recovered"] += 1
            by_field[typ + "/" + row["field"]]["exact_recovered"] += 1
    for key, (row, _) in targets.items():
        if key not in checked:
            review.append(mark(row, "target_record_missing"))
    if hash_file(TARGET) != expected:
        raise RuntimeError("Converted ESM changed during verification")
    assignments = {(r["target_formid"], r["record_type"], r["field"], r["target_field_occurrence_index"]) for r in recovered}
    if len(assignments) != len(recovered):
        raise RuntimeError("New assignment target collision")
    recovered.sort(key=lambda r: (r["target_formid"], r["record_type"], r["field"], r["target_field_occurrence_index"]))
    def save(file, rows):
        with gzip.open(DATA / file, "wt", encoding="utf-8", compresslevel=6) as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    save("xtranslator_fo3_provenance_exact.jsonl.gz", recovered)
    save("xtranslator_fo3_provenance_review.jsonl.gz", review)
    report = {
        "game": "fo3", "converted_esm_sha256": expected,
        "source_esm_sha256": source_sha, "source_sst_sha256": sst_sha,
        "source_plugin_owner_indices": owner_counts,
        "mapping_offsets": {k: f"0x{v:08X}" for k, v in PLUGIN_OFFSETS.items()},
        "scope": "Only previously-unplanned xTranslator missing_translation_match rows in known FO3+DLC display fields",
        "exact_recovered": len(recovered), "review_count": len(review),
        "reason_counts": dict(stats),
        "by_field": {k: dict(v) for k, v in sorted(by_field.items())},
        "recovered_examples": [{"target": r["target_formid"], "type": r["record_type"], "field": r["field"], "source": r["source_plugin"] + ":" + r["source_local_id"], "english": r["english"][:80]} for r in recovered[:15]],
        "caveat": "Exact static ESM and SST provenance only. Conversion offsets are based on previously observed mappings and revalidated per original/target record. Runtime reachability and creation/application of a localized patch are separate.",
    }
    (DATA / "xtranslator_fo3_provenance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"exact_recovered": len(recovered), "review_count": len(review), "reasons": stats.most_common(), "fields": [(k, v["exact_recovered"]) for k, v in by_field.items() if v["exact_recovered"]]}, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    run()
