"""Synthetic tests only: never edit a game installation."""
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import build_localized_esm_copy as builder


def field(tag, content):
    raw = content.encode("utf-8") + b"\0"
    return struct.pack("<4sH", tag, len(raw)) + raw


def record(tag, fid, content, compress=False):
    flags = 0x00040000 if compress else 0
    if compress:
        content = struct.pack("<I", len(content)) + zlib.compress(content)
    return struct.pack("<4sIIIII", tag, len(content), flags, fid, 0, 131) + content


def group(parts):
    data = b"".join(parts)
    return struct.pack("<4sI4sIII", b"GRUP", len(data) + 24, b"INFO", 0, 0, 0) + data


class TestConvertedEsmCopy(unittest.TestCase):
    def test_nested_groups_and_exact_fields(self):
        en1 = "This is a dialogue"
        en2 = "Terminal body"
        r1 = record(b"INFO", 0x01000001, field(b"NAM1", en1), compress=True)
        r2 = record(b"TERM", 0x01000002, field(b"UNAM", en2))
        untouched = record(b"NPC_", 0x01000003, field(b"FULL", "English ignored"))
        nested = group([group([r1, r2]), untouched])
        original = record(b"TES4", 0, field(b"CNAM", "owner")) + nested
        assignments = {
            (0x01000001, "INFO", "NAM1", 0): (en1, "대사가 표시됩니다"),
            (0x01000002, "TERM", "UNAM", 0): (en2, "터미널 본문"),
        }
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "source.esm"
            dst = Path(td) / "translated.esm"
            src.write_bytes(original)
            report = builder.write_copy(src, dst, assignments)
            self.assertEqual(report["changed_fields"], 2)
            self.assertEqual(report["groups_closed"], 2)
            self.assertEqual(src.read_bytes(), original)
            converted = dst.read_bytes()
            self.assertTrue(converted.startswith(original[: 24 + len(field(b"CNAM", "owner"))]))
            # Independent structural scan: GRUP boundaries must match the new size.
            first_group_offset = 24 + len(field(b"CNAM", "owner"))
            self.assertEqual(
                struct.unpack_from("<I", converted, first_group_offset + 4)[0],
                len(converted) - first_group_offset,
            )
            inner_offset = first_group_offset + 24
            self.assertGreater(struct.unpack_from("<I", converted, inner_offset + 4)[0], 24)
            rec_offset = inner_offset + 24
            typ, n, flags, fid, *_ = struct.unpack_from("<4sIIIII", converted, rec_offset)
            self.assertEqual((typ, fid), (b"INFO", 0x01000001))
            self.assertTrue(flags & 0x00040000)
            payload = converted[rec_offset + 24 : rec_offset + 24 + n]
            self.assertIn("대사가 표시됩니다".encode(), zlib.decompress(payload[4:]))
            second = rec_offset + 24 + n
            typ, n, _, fid, *_ = struct.unpack_from("<4sIIIII", converted, second)
            self.assertEqual((typ, fid), (b"TERM", 0x01000002))
            self.assertIn("터미널 본문".encode(), converted[second + 24 : second + 24 + n])
            self.assertTrue(converted.endswith(untouched))

    def test_xxxx_preserves_long_subrecord(self):
        old = "Y" * 66000
        raw = old.encode() + b"\0"
        long_field = struct.pack("<4sHI4sH", b"XXXX", 4, len(raw), b"UNAM", 0) + raw
        input_record = record(b"TERM", 0x01000008, long_field)
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td) / "a.esm", Path(td) / "b.esm"
            src.write_bytes(input_record)
            report = builder.write_copy(src, dst, {
                (0x01000008, "TERM", "UNAM", 0): (old, "한" * 23000)
            })
            self.assertEqual(report["changed_fields"], 1)
            patched = dst.read_bytes()
            self.assertEqual(patched[24:28], b"XXXX")
            self.assertEqual(struct.unpack_from("<I", patched, 24 + 6)[0], 69001)
            self.assertEqual(patched[34:38], b"UNAM")

    def test_unmatched_english_blocks_output(self):
        src_rec = record(b"INFO", 0x01000009, field(b"NAM1", "real"))
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td) / "a.esm", Path(td) / "b.esm"
            src.write_bytes(src_rec)
            with self.assertRaisesRegex(ValueError, "English mismatch"):
                builder.write_copy(src, dst, {
                    (0x01000009, "INFO", "NAM1", 0): ("wrong", "번역")
                })


if __name__ == "__main__":
    unittest.main()
