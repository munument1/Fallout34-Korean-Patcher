"""Regression checks for the narrowly scoped 0.9.102 binary experiment."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from tools.patch_fallout34_09102_utf8 import (
    SOURCE_CODEC_AFTER, SOURCE_CODEC_BEFORE, OUTPUT_CODEC_AFTER,
    OUTPUT_CODEC_BEFORE, GMST_CODEC_BEFORE, GMST_CODEC_AFTER, ORIGINAL_SHA256, patch_file, patched_bytes,
)


class ExperimentalUTF8BinaryPatch(unittest.TestCase):
    def test_targeted_function_only_and_same_length(self):
        data = (
            b"MZ" + b"cp1252\0" + SOURCE_CODEC_BEFORE
            + OUTPUT_CODEC_BEFORE + GMST_CODEC_BEFORE + b"something else cp1252\0"
        )
        output = patched_bytes(data)
        self.assertEqual(len(output), len(data))
        self.assertEqual(output.count(SOURCE_CODEC_AFTER), 1)
        self.assertEqual(output.count(OUTPUT_CODEC_AFTER), 1)
        self.assertEqual(output.count(GMST_CODEC_AFTER), 1)
        self.assertEqual(output.count(SOURCE_CODEC_BEFORE), 0)
        self.assertEqual(output.count(OUTPUT_CODEC_BEFORE), 0)
        self.assertEqual(output.count(b"cp1252\0"), 2)

    def test_wrong_layout_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected one"):
            patched_bytes(b"MZ cp1252")
        with self.assertRaisesRegex(ValueError, "found 2"):
            patched_bytes(SOURCE_CODEC_BEFORE + SOURCE_CODEC_BEFORE + OUTPUT_CODEC_BEFORE + GMST_CODEC_BEFORE)

    def test_guards_original_and_expecting_sha(self):
        with tempfile.TemporaryDirectory() as root:
            src = Path(root) / "source.exe"
            dest = Path(root) / "trial.exe"
            src.write_bytes(SOURCE_CODEC_BEFORE + OUTPUT_CODEC_BEFORE)
            with self.assertRaisesRegex(ValueError, "Expected unmodified"):
                patch_file(src, dest)
            self.assertFalse(dest.exists())
            with self.assertRaisesRegex(ValueError, "cannot be overwritten"):
                patch_file(src, src)
            self.assertEqual(len(ORIGINAL_SHA256), len(hashlib.sha256(b"").hexdigest()))

    def test_utf8_codec_alias_is_valid(self):
        sample = "중공군 장교의 검 / 스위치블레이드"
        self.assertEqual(sample.encode("utf-8").decode("utf-8 "), sample)


if __name__ == "__main__":
    unittest.main()
