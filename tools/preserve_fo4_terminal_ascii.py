"""Restore Share-TechMono's fixed-width hacking grid without losing Hangul."""
import struct
import zlib

from preserve_fo4_hud_digits import read_font, read_swf

FONT_ID = 6
ASCII = range(32, 127)


def terminal_font(tags):
    matches = [body for kind, body in tags
               if kind == 75 and body[:2] == struct.pack('<H', FONT_ID)]
    if len(matches) != 1:
        raise ValueError('Expected exactly one terminal font 6')
    font = read_font(matches[0], FONT_ID)
    if font['prefix'][5:-2].rstrip(b'\0') != b'Share-TechMono':
        raise ValueError('Unexpected terminal font alias')
    if font['kerning'] != b'\0\0':
        raise ValueError('Terminal kerning requires explicit handling')
    return font


def preserve_terminal_ascii(source, rebuilt):
    """Copy original printable ASCII shapes, advances and bounds into font 6.

    Source must have fixed-width ASCII (the pre-Noto bundle or a fixed build).
    All other glyphs, including 11,172 Noto Hangul syllables, remain unchanged.
    """
    original = terminal_font(read_swf(source)[1])
    header, tags = read_swf(rebuilt)
    current = terminal_font(tags)
    source_indices = {c: original['codes'].index(c) for c in ASCII}
    if len({original['advances'][i] for i in source_indices.values()}) != 1:
        raise ValueError('Source terminal ASCII is not fixed-width; use pre-Noto or fixed SWF')
    if original['metrics'] != current['metrics']:
        raise ValueError('Terminal vertical metrics changed')
    for code, j in source_indices.items():
        i = current['codes'].index(code)
        for key in ('shapes', 'advances', 'bounds'):
            current[key][i] = original[key][j]
    count = len(current['codes'])
    offsets = [(count + 1) * struct.calcsize(current['offsets'])]
    for shape in current['shapes']:
        offsets.append(offsets[-1] + len(shape))
    body = current['prefix'] + struct.pack('<' + current['offsets'] * (count + 1), *offsets)
    body += b''.join(current['shapes'])
    body += struct.pack('<' + current['code_fmt'] * count, *current['codes'])
    body += current['metrics'] + struct.pack('<' + 'H' * count, *current['advances'])
    body += b''.join(current['bounds']) + current['kerning']
    if read_font(body, FONT_ID) != current:
        raise ValueError('Rebuilt terminal font validation failed')
    payload = bytearray(header[8:])
    for kind, contents in tags:
        if kind == 75 and contents[:2] == struct.pack('<H', FONT_ID):
            contents = body
        payload.extend(struct.pack('<HI', kind << 6 | 63, len(contents)))
        payload.extend(contents)
    rebuilt.write_bytes(b'CWS' + header[3:4] + struct.pack('<I', len(payload) + 8)
                        + zlib.compress(payload, 9))
