"""Independent, byte-level audit of a locally translated Fallout34 ESM copy.

Compare original and output records in order; every subrecord except an explicitly
assigned string must have identical bytes, including compressed-record content.
Validate every nested GRUP length and ensure each translation appears exactly once.
"""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

from build_localized_esm_copy import DEFAULT_ESM, ROOT, load_assignments, sha256


def events(path):
    with path.open("rb") as fp:
        size = path.stat().st_size
        pos = 0
        levels = []
        while pos < size:
            while levels and levels[-1] == pos:
                levels.pop()
                yield ("group_end",)
            if levels and pos > levels[-1]:
                raise ValueError("GRUP boundary overrun")
            h = fp.read(24)
            if len(h) != 24:
                raise ValueError(f"Invalid header at {pos}")
            tag, n, flags, fid, rev, ver = struct.unpack("<4sIIIII", h)
            if tag == b"GRUP":
                if n < 24 or pos + n > size or levels and pos + n > levels[-1]:
                    raise ValueError(f"Invalid group at {pos}")
                levels.append(pos + n)
                pos += 24
                yield ("group_start", h[8:])
                continue
            if n > 64 * 1024 * 1024 or pos + 24 + n > size or levels and pos + 24 + n > levels[-1]:
                raise ValueError(f"Invalid record at {pos}")
            content = fp.read(n)
            if flags & 0x00040000:
                if len(content) < 4:
                    raise ValueError("Compressed record too short")
                length = struct.unpack_from("<I", content)[0]
                content = zlib.decompress(content[4:])
                if len(content) != length:
                    raise ValueError("Compressed record length mismatch")
            pos += 24 + n
            yield ("record", (tag, fid, flags, rev, ver), content)
        while levels and levels[-1] == pos:
            levels.pop()
            yield ("group_end",)
        if levels:
            raise ValueError(f"Unterminated groups: {len(levels)}")


def subrecords(blob):
    offset = 0
    counter = Counter()
    while offset < len(blob):
        if len(blob) - offset < 6:
            raise ValueError("Truncated subrecord")
        tag, n = struct.unpack_from("<4sH", blob, offset)
        offset += 6
        if tag == b"XXXX":
            if n != 4 or len(blob) - offset < 10:
                raise ValueError("Invalid XXXX")
            n = struct.unpack_from("<I", blob, offset)[0]
            offset += 4
            tag, _ = struct.unpack_from("<4sH", blob, offset)
            offset += 6
        if offset + n > len(blob):
            raise ValueError("Invalid subrecord length")
        name = tag.decode("ascii", "replace")
        index = counter[name]
        counter[name] += 1
        yield (name, index), blob[offset:offset + n]
        offset += n


def verify(original: Path, translated: Path, assignments):
    old = events(original)
    new = events(translated)
    tally = Counter()
    translated_keys = set()
    while True:
        a = next(old, None)
        b = next(new, None)
        if a is None or b is None:
            if a != b:
                raise ValueError("Event count mismatch")
            break
        if a[0] != b[0] or a[0] == "group_start" and a[1] != b[1]:
            raise ValueError(f"Group/record layout changed: {a[0]} vs {b[0]}")
        if a[0] != "record":
            tally[a[0]] += 1
            continue
        if a[1] != b[1]:
            raise ValueError(f"Record metadata changed: {a[1]} vs {b[1]}")
        tag, fid, _, _, _ = a[1]
        typ = tag.decode("ascii", "replace")
        old_fields = list(subrecords(a[2]))
        new_fields = list(subrecords(b[2]))
        if len(old_fields) != len(new_fields):
            raise ValueError(f"Subrecord count changed at {fid:08X}")
        for (old_id, before), (new_id, after) in zip(old_fields, new_fields):
            if old_id != new_id:
                raise ValueError(f"Subrecord identity changed at {fid:08X}")
            field, idx = old_id
            key = (fid, typ, field, idx)
            if key not in assignments:
                if before != after:
                    raise ValueError(f"Unplanned data mutation {key}")
                continue
            en, ko = assignments[key]
            source = en.encode("utf-8")
            target = ko.encode("utf-8")
            if before not in (source, source + b"\0"):
                # English input may be cp1252 rather than UTF-8.
                cp = en.encode("cp1252")
                if before not in (cp, cp + b"\0"):
                    raise ValueError(f"Unexpected original value at {key}")
            expected = target + (b"\0" if before.endswith(b"\0") else b"")
            if after != expected:
                raise ValueError(f"Unexpected Korean output at {key}")
            if key in translated_keys:
                raise ValueError(f"Repeated FormID key {key}")
            translated_keys.add(key)
            tally["verified_fields"] += 1
        tally["verified_records"] += 1
    if translated_keys != assignments.keys():
        raise ValueError(f"Missing {len(assignments.keys() - translated_keys)} translation targets")
    return dict(tally)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=("fo3", "fnv"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--translated", type=Path, required=True)
    parser.add_argument("--extra-plan", action="append", type=Path, default=[])
    args = parser.parse_args()
    data = ROOT / "data" / args.game
    file_name = "Fallout34.esm" if args.game == "fo3" else "FalloutNV34.esm"
    source = (args.source or DEFAULT_ESM / file_name).resolve()
    target = args.translated.resolve()
    expected = json.loads((data / "indexed_plan_report.json").read_text("utf-8"))["esm_sha256"]
    if sha256(source) != expected:
        parser.error("Original ESM does not match pinned SHA256")
    plan, _ = load_assignments(data, [p.resolve() for p in args.extra_plan])
    stats = verify(source, target, plan)
    result = {
        "game": args.game,
        "source_sha256": expected,
        "translated_sha256": sha256(target),
        "verification": "pass",
        "stats": stats,
        "scope": "static byte-level record and subrecord comparison; not FO4 runtime validation",
    }
    (data / "localized_esm_copy_verify.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
