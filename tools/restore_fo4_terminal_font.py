"""Apply the terminal font hotfix from the versioned pre-Noto SWF."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from preserve_fo4_hud_digits import read_swf
from preserve_fo4_terminal_ascii import preserve_terminal_ascii, terminal_font

ROOT = Path(__file__).resolve().parents[1]
REL = 'Interface/fonts_en.swf'
SOURCE_COMMIT = 'eb398887d836c364ad72d52e9f5b06b7097a2f79'
SOURCE_SHA256 = '2a9499eef3ee02282625805579293e6d5b8a11be678476994e685e5bd013f099'


def apply():
    source = subprocess.check_output(
        ['git', 'show', f'{SOURCE_COMMIT}:assets/fo4_korean/{REL}'], cwd=ROOT)
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unexpected original font bundle')
    destination = ROOT / 'assets/fo4_korean' / REL
    index_path = ROOT / 'assets/fo4_korean_sources.json'
    index = json.loads(index_path.read_text('utf-8'))
    previous = hashlib.sha256(destination.read_bytes()).hexdigest()
    if previous != index['files'][REL]:
        raise ValueError('Bundled SWF does not match the asset index')
    before_header, before_tags = read_swf(destination)
    before_font = terminal_font(before_tags)
    with tempfile.TemporaryDirectory() as temp:
        original, fixed = Path(temp) / 'original.swf', Path(temp) / 'fixed.swf'
        original.write_bytes(source)
        fixed.write_bytes(destination.read_bytes())
        preserve_terminal_ascii(original, fixed)
        after_header, after_tags = read_swf(fixed)
        after_font = terminal_font(after_tags)
        # Every unrelated font, script and resource stays byte-identical.
        unrelated = lambda tags: [(t, b) for t, b in tags
                                  if not (t == 75 and b[:2] == b'\x06\x00')]
        if before_header[8:] != after_header[8:] or unrelated(before_tags) != unrelated(after_tags):
            raise ValueError('Unrelated SWF resources changed')
        if before_font['codes'] != after_font['codes']:
            raise ValueError('Terminal character set changed')
        for i, code in enumerate(before_font['codes']):
            if not 32 <= code <= 126:
                for key in ('shapes', 'advances', 'bounds'):
                    if before_font[key][i] != after_font[key][i]:
                        raise ValueError(f'Non-ASCII glyph changed: {code}')
        if sum(0xAC00 <= c <= 0xD7A3 for c in after_font['codes']) != 11172:
            raise ValueError('Full Hangul coverage missing')
        digest = hashlib.sha256(fixed.read_bytes()).hexdigest()
        report_path = ROOT / 'docs/FONT_REBUILD_REPORT.json'
        report = json.loads(report_path.read_text('utf-8'))
        entry = report['files'][REL]
        entry['result_sha256'] = digest
        entry['result_bytes'] = fixed.stat().st_size
        entry['terminal_ascii_restoration'] = {
            'font_id': 6, 'font_name': 'Share-TechMono',
            'codepoints': 'U+0020-U+007E', 'glyph_count': 95,
            'advance_in_definefont3_units': 11060,
            'source_commit': SOURCE_COMMIT, 'source_sha256': SOURCE_SHA256,
            'unchanged_non_ascii_glyphs': True,
            'unchanged_other_fonts_and_non_font_tags': True,
            'in_game_verified': False,
        }
        destination.write_bytes(fixed.read_bytes())
        index['files'][REL] = digest
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Terminal font restored: {digest}')


if __name__ == '__main__':
    apply()
