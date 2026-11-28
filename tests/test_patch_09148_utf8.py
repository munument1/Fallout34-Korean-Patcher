import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from patch_fallout34_09148_utf8 import (READ_BEFORE, READ_AFTER, OUTPUT_CODEC_BEFORE,
                                        OUTPUT_CODEC_AFTER, GMST_CODEC_BEFORE, GMST_CODEC_AFTER,
                                        patched_bytes)


class Experimental09148Patch(unittest.TestCase):
    def test_only_three_verified_codec_constants_change(self):
        original = b'begin' + READ_BEFORE + b'middle' + OUTPUT_CODEC_BEFORE + GMST_CODEC_BEFORE + b'end'
        result = patched_bytes(original)
        self.assertEqual(len(original), len(result))
        self.assertEqual(result, b'begin' + READ_AFTER + b'middle' + OUTPUT_CODEC_AFTER + GMST_CODEC_AFTER + b'end')
        self.assertEqual('한글'.encode('utf-8 ').decode('utf-8 '), '한글')

    def test_missing_or_duplicate_anchor_is_rejected(self):
        with self.assertRaises(ValueError):
            patched_bytes(READ_BEFORE + OUTPUT_CODEC_BEFORE)
        with self.assertRaises(ValueError):
            patched_bytes(READ_BEFORE * 2 + OUTPUT_CODEC_BEFORE + GMST_CODEC_BEFORE)
