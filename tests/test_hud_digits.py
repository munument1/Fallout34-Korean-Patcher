import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from preserve_fo4_hud_digits import preserve_hud_digits, read_font, read_swf


def sample_swf(path, advance):
    codes = list(range(48, 58)) + [0xAC00]
    count = len(codes)
    shape = b'\x10\x00' if advance == 500 else b'\x00\x00'
    prefix = struct.pack('<HBBB', 7, 0x8D, 0, 4) + b'HUD\0' + struct.pack('<H', count)
    offsets = [(count + 1) * 4 + i * len(shape) for i in range(count + 1)]
    body = prefix + struct.pack('<' + 'I' * (count + 1), *offsets) + shape * count
    body += struct.pack('<' + 'H' * count, *codes) + struct.pack('<HHh', 1000, 200, 0)
    body += struct.pack('<' + 'H' * count, *([advance] * count)) + b'\0' * count + b'\0\0'
    payload = b'\x08\x00\x00\x18\x01\x00'
    for kind, contents in [(75, body), (9, b'\x00\xff\x00'), (0, b'')]:
        payload += struct.pack('<HI', kind << 6 | 63, len(contents)) + contents
    path.write_bytes(b'FWS\x08' + struct.pack('<I', len(payload) + 8) + payload)


class HudDigitTests(unittest.TestCase):
    def test_preserves_digits_without_reverting_other_glyphs_or_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, rebuilt = Path(tmp) / 'old.swf', Path(tmp) / 'new.swf'
            sample_swf(source, 500)
            sample_swf(rebuilt, 700)
            _, before = read_swf(rebuilt)
            preserve_hud_digits(source, rebuilt)
            _, after = read_swf(rebuilt)
            font = read_font(after[0][1])
            self.assertEqual(font['advances'], [500] * 10 + [700])
            self.assertEqual(before[1:], after[1:])
            self.assertEqual(font['shapes'][:10], read_font(read_swf(source)[1][0][1])['shapes'][:10])
            self.assertEqual(font['shapes'][10:], read_font(before[0][1])['shapes'][10:])
            preserve_hud_digits(source, rebuilt)
            self.assertEqual(after, read_swf(rebuilt)[1])
