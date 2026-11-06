"""Build a LOCAL, translated COPY of an owned Fallout34 converted ESM.

This does NOT modify the installed source ESM, and must never be used to publish
game assets. It validates the original ESM SHA256 before writing, and uses only
FormID/record/subrecord-index/English verified assignments from versioned plans.
GRUP byte sizes and compressed records are rebuilt when necessary.

Example:
  python tools/build_localized_esm_copy.py fo3 --output work/fo3/localized/Data/Fallout34.esm
  python tools/build_localized_esm_copy.py fnv --output work/fnv/localized/Data/FalloutNV34.esm
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ESM = Path(r"C:\Games\Steam\steamapps\common\Fallout 4\Data")
BASE_PLANS = (
    "indexed_patch_plan_candidates.jsonl.gz",
    "indexed_patch_plan_v2_strict_extra.jsonl.gz",
)
RECORD_HEADER = struct.Struct("<4sIIIII")
FIELD_HEADER = struct.Struct("<4sH")
MAX_RECORD = 64 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for buf in iter(lambda: fp.read(8 * 1024 * 1024), b""):
            digest.update(buf)
    return digest.hexdigest()


def load_assignments(folder: Path, extra: list[Path]) -> tuple[dict, Counter]:
    assignments = {}
    counts = Counter()
    for path in [*(folder / p for p in BASE_PLANS), *extra]:
        with gzip.open(path, "rt", encoding="utf-8") as fp:
            for line in fp:
                rec = json.loads(line)
                idx = int(rec["target_field_occurrence_index"])
                key = (
                    int(rec["target_formid"], 16),
                    rec["record_type"],
                    rec["field"],
                    idx,
                )
                value = (rec["english"], rec["korean"])
                if not value[0] or not value[1] or value[0] == value[1]:
                    raise ValueError(f"Empty or untranslated assignment {key}")
                if "\ufffd" in value[1]:
                    raise ValueError(f"Corrupted Korean U+FFFD at {key}")
                prior = assignments.get(key)
                if prior is not None and prior != value:
                    raise ValueError(f"Conflicting assignments at {key}")
                if prior is None:
                    assignments[key] = value
                    counts[path.name] += 1
    return assignments, counts


def read_plain_string(raw: bytes) -> str | None:
    if not raw or b"\0" in raw[:-1]:
        return None
    src = raw[:-1] if raw.endswith(b"\0") else raw
    for encoding in ("utf-8", "cp1252"):
        try:
            return src.decode(encoding)
        except UnicodeError:
            pass
    return None


def replace_fields(data: bytes, fid: int, typ: str, assignments: dict, seen: set):
    """Preserve every untouched subrecord byte for byte; support XXXX long fields."""
    offset = 0
    field_count = Counter()
    out = bytearray()
    changes = 0
    while offset < len(data):
        start = offset
        if len(data) - offset < 6:
            raise ValueError(f"Truncated subrecord {typ}:{fid:08X}")
        field, short_size = FIELD_HEADER.unpack_from(data, offset)
        offset += 6
        extended = False
        if field == b"XXXX":
            if short_size != 4 or len(data) - offset < 10:
                raise ValueError(f"Invalid XXXX at {typ}:{fid:08X}")
            extended_size = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            field, short_size = FIELD_HEADER.unpack_from(data, offset)
            offset += 6
            extended = True
            size = extended_size
        else:
            size = short_size
        if size < 0 or size > len(data) - offset:
            raise ValueError(f"Bad subrecord length at {typ}:{fid:08X}")
        raw = data[offset : offset + size]
        offset += size
        name = field.decode("ascii", "replace")
        idx = field_count[name]
        field_count[name] += 1
        key = (fid, typ, name, idx)
        if key not in assignments:
            out.extend(data[start:offset])
            continue
        english, korean = assignments[key]
        actual = read_plain_string(raw)
        if actual != english:
            raise ValueError(f"English mismatch at {key}: {actual!r} != {english!r}")
        if key in seen:
            raise ValueError(f"Duplicate assignment target record {key}")
        seen.add(key)
        new = korean.encode("utf-8") + (b"\0" if raw.endswith(b"\0") else b"")
        if extended or len(new) > 0xFFFF:
            out.extend(FIELD_HEADER.pack(b"XXXX", 4) + struct.pack("<I", len(new)))
            out.extend(FIELD_HEADER.pack(field, 0))
        else:
            out.extend(FIELD_HEADER.pack(field, len(new)))
        out.extend(new)
        changes += 1
    return bytes(out), changes


def write_copy(src: Path, dst: Path, assignments: dict) -> dict:
    """Stream records, and backpatch nested GRUP byte lengths on close."""
    entries = {(fid, typ) for fid, typ, _, _ in assignments}
    stats = Counter()
    seen = set()
    original_bytes = src.stat().st_size
    with src.open("rb") as inp, dst.open("w+b") as out:
        pos = 0
        stack = []  # input_end, output_begin
        while pos < original_bytes:
            while stack and stack[-1][0] == pos:
                _, output_begin = stack.pop()
                end_pos = out.tell()
                group_size = end_pos - output_begin
                if group_size > 0xFFFFFFFF:
                    raise ValueError("GRUP size overflow")
                out.seek(output_begin + 4)
                out.write(struct.pack("<I", group_size))
                out.seek(end_pos)
                stats["groups_closed"] += 1
            if stack and pos > stack[-1][0]:
                raise ValueError("Input crosses GRUP boundary")
            header = inp.read(24)
            if len(header) != 24:
                raise ValueError(f"Truncated record header at {pos}")
            tag, size, flags, fid, revision, version = RECORD_HEADER.unpack(header)
            if tag == b"GRUP":
                if size < 24 or pos + size > original_bytes:
                    raise ValueError(f"Invalid GRUP at {pos}")
                if stack and pos + size > stack[-1][0]:
                    raise ValueError(f"GRUP exceeds parent at {pos}")
                stack.append((pos + size, out.tell()))
                out.write(header)
                pos += 24
                stats["groups"] += 1
                continue
            if size > MAX_RECORD or pos + 24 + size > original_bytes:
                raise ValueError(f"Invalid record {tag!r}:{fid:08X}")
            if stack and pos + 24 + size > stack[-1][0]:
                raise ValueError(f"Record crosses GRUP at {pos}")
            stats["records"] += 1
            typ = tag.decode("ascii", "replace")
            # Untouched records are copied as-is, including their compression data.
            if (fid, typ) not in entries:
                out.write(header)
                remaining = size
                while remaining:
                    chunk = inp.read(min(remaining, 4 * 1024 * 1024))
                    if not chunk:
                        raise ValueError("Truncated record data")
                    out.write(chunk)
                    remaining -= len(chunk)
                pos += 24 + size
                continue
            payload = inp.read(size)
            if len(payload) != size:
                raise ValueError("Truncated target record")
            compressed = bool(flags & 0x00040000)
            if compressed:
                if len(payload) < 4:
                    raise ValueError("Compressed record has no expected size")
                original_len = struct.unpack_from("<I", payload)[0]
                decoded = zlib.decompress(payload[4:])
                if len(decoded) != original_len:
                    raise ValueError(f"Invalid compressed record {typ}:{fid:08X}")
            else:
                decoded = payload
            changed, count = replace_fields(decoded, fid, typ, assignments, seen)
            if count:
                stats["changed_records"] += 1
                stats["changed_fields"] += count
                if compressed:
                    payload = struct.pack("<I", len(changed)) + zlib.compress(changed)
                else:
                    payload = changed
                header = RECORD_HEADER.pack(tag, len(payload), flags, fid, revision, version)
            out.write(header)
            out.write(payload)
            pos += 24 + size
        while stack and stack[-1][0] == pos:
            _, output_begin = stack.pop()
            end_pos = out.tell()
            out.seek(output_begin + 4)
            out.write(struct.pack("<I", end_pos - output_begin))
            out.seek(end_pos)
            stats["groups_closed"] += 1
        if stack:
            raise ValueError(f"Unclosed GRUPs: {stack}")
        if seen != assignments.keys():
            missing = list(assignments.keys() - seen)
            raise ValueError(f"{len(missing)} plan targets missing, sample {missing[:5]}")
    return {**stats, "original_bytes": original_bytes, "translated_bytes": dst.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=("fo3", "fnv"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--extra-plan", action="append", type=Path, default=[])
    args = parser.parse_args()
    data = ROOT / "data" / args.game
    source = (args.source or DEFAULT_ESM / ("Fallout34.esm" if args.game == "fo3" else "FalloutNV34.esm")).resolve()
    target = args.output.resolve()
    if source == target or target.exists():
        parser.error("Output MUST be a new path distinct from the original ESM (no overwrites)")
    expected = json.loads((data / "indexed_plan_report.json").read_text("utf-8"))["esm_sha256"]
    current = sha256(source)
    if current != expected:
        parser.error(f"Source ESM hash mismatch: {current}, expected {expected}")
    assignments, plan_count = load_assignments(data, [p.resolve() for p in args.extra_plan])
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    if temporary.exists():
        parser.error(f"Stale temporary output must be inspected before retrying: {temporary}")
    try:
        report = write_copy(source, temporary, assignments)
        if report["changed_fields"] != len(assignments):
            raise ValueError("Not all assignments were applied")
        translated_sha = sha256(temporary)
        temporary.replace(target)
    except BaseException:
        if temporary.exists():
            temporary.unlink()
        raise
    output_report = {
        "game": args.game,
        "source": str(source),
        "source_sha256": current,
        "output": str(target),
        "output_sha256": translated_sha,
        "plans": dict(plan_count),
        "counts": report,
        "warning": "Local preview only. Converted ESM original untouched. In-game and load order QA NOT completed. Do not redistribute converted ESM.",
    }
    report_path = data / "localized_esm_copy_report.json"
    report_path.write_text(json.dumps(output_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output_report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
