import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from preserve_fo4_hud_digits import read_swf
from preserve_fo4_terminal_ascii import preserve_terminal_ascii, terminal_font


class TerminalFontTests(unittest.TestCase):
    def test_bundled_terminal_has_original_ascii_and_full_hangul(self):
        font = terminal_font(read_swf(ROOT / 'assets/fo4_korean/Interface/fonts_en.swf')[1])
        # Fingerprint from the pre-Noto SWF at eb398887d836c364ad72d52e9f5b06b7097a2f79.
        digest = hashlib.sha256()
        for code in range(32, 127):
            i = font['codes'].index(code)
            self.assertEqual(font['advances'][i], 11060)
            for key in ('shapes', 'bounds'):
                digest.update(struct.pack('<I', len(font[key][i])) + font[key][i])
            digest.update(struct.pack('<H', font['advances'][i]))
        self.assertEqual(digest.hexdigest(), '29358a252c9dc33e83845a780f4f751c1082e24c06c081d1486802eb34c56de4')
        self.assertTrue(set(range(0xAC00, 0xD7A4)).issubset(font['codes']))

    def test_preservation_restores_variable_ascii_without_touching_hangul_or_other_tags(self):
        source = ROOT / 'assets/fo4_korean/Interface/fonts_en.swf'
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'rebuilt.swf'
            header, tags = read_swf(source)
            modified = []
            for kind, body in tags:
                if kind == 75 and body[:2] == b'\x06\x00':
                    body = bytearray(body)
                    base = 7 + body[4]
                    count = struct.unpack_from('<H', body, base - 2)[0]
                    code_offset = struct.unpack_from('<I', body, base + count * 4)[0]
                    font = terminal_font(tags)
                    advances = base + code_offset + count * 2 + 6
                    for c in (ord('i'), ord('W')):
                        struct.pack_into('<H', body, advances + font['codes'].index(c) * 2, 17000)
                    body = bytes(body)
                modified.append((kind, body))
            payload = header[8:] + b''.join(struct.pack('<HI', k << 6 | 63, len(b)) + b for k, b in modified)
            target.write_bytes(b'FWS' + header[3:4] + struct.pack('<I', len(payload) + 8) + payload)
            self.assertNotEqual(read_swf(target)[1], tags)
            with self.assertRaisesRegex(ValueError, 'not fixed-width'):
                preserve_terminal_ascii(target, source)
            preserve_terminal_ascii(source, target)
            # Exact comparison includes Hangul, HUD digits, other fonts and all resources.
            self.assertEqual(read_swf(target)[1], tags)
