"""Preserve the tested Roboto Condensed Bold digits when rebuilding fonts."""
import struct
import zlib


def read_swf(path):
    data = path.read_bytes()
    if data[:3] == b'CWS':
        data = b'FWS' + data[3:8] + zlib.decompress(data[8:])
    if data[:3] != b'FWS' or len(data) != struct.unpack_from('<I', data, 4)[0]:
        raise ValueError('Invalid SWF')
    start = 8 + (5 + 4 * (data[8] >> 3) + 7) // 8 + 4
    pos, tags = start, []
    while pos < len(data):
        head = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        kind, size = head >> 6, head & 63
        if size == 63:
            size = struct.unpack_from('<I', data, pos)[0]
            pos += 4
        body = data[pos:pos + size]
        if len(body) != size:
            raise ValueError('Truncated SWF tag')
        tags.append((kind, body))
        pos += size
    return data[:start], tags


def read_font(body):
    # Only the known DefineFont3 HUD face is accepted, including its bold flag.
    if struct.unpack_from('<H', body)[0] != 7 or not body[2] & 1 or not body[2] & 128:
        raise ValueError('Expected HUD bold font 7 with layout')
    base = 7 + body[4]
    count = struct.unpack_from('<H', body, base - 2)[0]
    offset_fmt = 'I' if body[2] & 8 else 'H'
    code_fmt = 'H' if body[2] & 4 else 'B'
    offsets = struct.unpack_from('<' + offset_fmt * (count + 1), body, base)
    shapes = [body[base + offsets[i]:base + offsets[i + 1]] for i in range(count)]
    codes = struct.unpack_from('<' + code_fmt * count, body, base + offsets[-1])
    layout = base + offsets[-1] + struct.calcsize(code_fmt) * count
    advances = list(struct.unpack_from('<' + 'H' * count, body, layout + 6))
    pos, bounds = layout + 6 + 2 * count, []
    for _ in range(count):
        size = (5 + 4 * (body[pos] >> 3) + 7) // 8
        bounds.append(body[pos:pos + size])
        pos += size
    kerning = body[pos:]
    n = struct.unpack_from('<H', kerning)[0]
    pair_fmt = '<' + code_fmt * 2 + 'h'
    if len(kerning) != 2 + n * struct.calcsize(pair_fmt):
        raise ValueError('Invalid font layout')
    for pair in struct.iter_unpack(pair_fmt, kerning[2:]):
        if any(48 <= c <= 57 for c in pair[:2]):
            raise ValueError('Digit kerning requires explicit handling')
    return dict(prefix=body[:base], offsets=offset_fmt, code_fmt=code_fmt,
                codes=codes, shapes=shapes, advances=advances, bounds=bounds,
                metrics=body[layout:layout + 6], kerning=kerning)


def preserve_hud_digits(source, rebuilt):
    """Copy digit outlines and layout from source; keep every other glyph/tag."""
    _, source_tags = read_swf(source)
    header, tags = read_swf(rebuilt)
    def hud_body(items):
        matches = [b for t, b in items if t == 75 and b[:2] == b'\x07\x00']
        if len(matches) != 1:
            raise ValueError('Expected exactly one HUD font')
        return matches[0]
    old, current = read_font(hud_body(source_tags)), read_font(hud_body(tags))
    if old['prefix'][5:-2] != current['prefix'][5:-2]:
        raise ValueError('HUD font alias changed')
    for code in range(48, 58):
        i, j = current['codes'].index(code), old['codes'].index(code)
        for key in ('shapes', 'advances', 'bounds'):
            current[key][i] = old[key][j]
    count = len(current['codes'])
    offsets = [(count + 1) * struct.calcsize(current['offsets'])]
    for shape in current['shapes']:
        offsets.append(offsets[-1] + len(shape))
    body = current['prefix'] + struct.pack('<' + current['offsets'] * (count + 1), *offsets)
    body += b''.join(current['shapes'])
    body += struct.pack('<' + current['code_fmt'] * count, *current['codes'])
    body += current['metrics'] + struct.pack('<' + 'H' * count, *current['advances'])
    body += b''.join(current['bounds']) + current['kerning']
    if read_font(body) != current:
        raise ValueError('Rebuilt font validation failed')
    payload = header[8:]
    for kind, contents in tags:
        if kind == 75 and contents[:2] == b'\x07\x00':
            contents = body
        payload += struct.pack('<HI', kind << 6 | 63, len(contents)) + contents
    rebuilt.write_bytes(b'CWS' + header[3:4] + struct.pack('<I', len(payload) + 8)
                        + zlib.compress(payload, 9))
