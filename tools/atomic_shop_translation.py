"""Patch reviewed AS3 display literals in the exact supported Atomic Shop SWF."""
from __future__ import annotations

from collections import Counter
import struct
import zlib


def _read_u30(data, pos):
    value = 0
    for index in range(5):
        if pos >= len(data):
            raise ValueError('Truncated ABC number')
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << (index * 7)
        if not byte & 128:
            return value, pos
    raise ValueError('Invalid ABC number')


def _write_u30(value):
    if not 0 <= value < 1 << 30:
        raise ValueError('Invalid ABC string length')
    out = bytearray()
    while value >= 128:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def _abc_strings(abc, translations, hits):
    if len(abc) < 4:
        raise ValueError('Truncated ABC header')
    pos = 4
    for kind in ('int', 'uint', 'double'):
        count, pos = _read_u30(abc, pos)
        for _ in range(1, count):
            if kind == 'double':
                pos += 8
                if pos > len(abc):
                    raise ValueError('Truncated ABC double')
            else:
                _, pos = _read_u30(abc, pos)
    count, start = _read_u30(abc, pos)
    out = bytearray(abc[:start])
    pos = start
    for _ in range(1, count):
        length, pos = _read_u30(abc, pos)
        if pos + length > len(abc):
            raise ValueError('Truncated ABC string')
        value = abc[pos:pos+length].decode('utf8')
        pos += length
        if value in translations:
            hits[value] += 1
            value = translations[value]
        encoded = value.encode('utf8')
        out.extend(_write_u30(len(encoded)))
        out.extend(encoded)
    out.extend(abc[pos:])
    return bytes(out)


def _unpack_swf(data):
    if len(data) < 8 or data[:3] not in (b'FWS', b'CWS'):
        raise ValueError('Unsupported SWF')
    body = zlib.decompress(data[8:]) if data[:3] == b'CWS' else data[8:]
    if len(body) + 8 != struct.unpack_from('<I', data, 4)[0]:
        raise ValueError('Invalid SWF length')
    return body


def _rewrite(data, translations):
    body = _unpack_swf(data)
    rect_size = (5 + 4 * (body[0] >> 3) + 7) // 8
    pos = rect_size + 4
    out = bytearray(body[:pos])
    hits = Counter()
    abc_count = 0
    while pos < len(body):
        start = pos
        if pos + 2 > len(body):
            raise ValueError('Truncated SWF tag')
        tag_header = struct.unpack_from('<H', body, pos)[0]
        pos += 2
        kind, size = tag_header >> 6, tag_header & 63
        long_tag = size == 63
        if long_tag:
            if pos + 4 > len(body):
                raise ValueError('Truncated SWF tag length')
            size = struct.unpack_from('<I', body, pos)[0]
            pos += 4
        if pos + size > len(body):
            raise ValueError('SWF tag exceeds file')
        tag = body[pos:pos+size]
        pos += size
        if kind != 82:
            out.extend(body[start:pos])
            continue
        if len(tag) < 5:
            raise ValueError('Truncated DoABC tag')
        name_end = tag.index(b'\0', 4) + 1
        tag = tag[:name_end] + _abc_strings(tag[name_end:], translations, hits)
        abc_count += 1
        if long_tag or len(tag) >= 63:
            out.extend(struct.pack('<HI', kind << 6 | 63, len(tag)))
        else:
            out.extend(struct.pack('<H', kind << 6 | len(tag)))
        out.extend(tag)
    if abc_count != 1 or set(hits) != set(translations) or any(n != 1 for n in hits.values()):
        raise ValueError(f'Unexpected SWF display strings: {len(hits)}/{len(translations)}')
    raw = bytes(out)
    header = data[:4] + struct.pack('<I', len(raw) + 8)
    return header + (zlib.compress(raw, 9) if data[:3] == b'CWS' else raw)


def translate_swf(data, translations):
    if len(set(translations.values())) != len(translations):
        raise ValueError('Atomic Shop translations must be uniquely reversible')
    translated = _rewrite(data, translations)
    restored = _rewrite(translated, {value: key for key, value in translations.items()})
    if data[:4] != restored[:4] or _unpack_swf(data) != _unpack_swf(restored):
        raise ValueError('SWF round-trip verification failed')
    return translated
