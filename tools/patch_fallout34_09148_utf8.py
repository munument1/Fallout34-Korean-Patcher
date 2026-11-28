"""Make an experimental local UTF-8 converter copy for exactly version 0.9.148.

This does not implement a UTF-8/CP1252 fallback and must not be used on a
different binary. The original installer is never modified or redistributed.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path

from patch_fallout34_09102_utf8 import OUTPUT_CODEC_BEFORE, OUTPUT_CODEC_AFTER, GMST_CODEC_BEFORE, GMST_CODEC_AFTER

ORIGINAL_SHA256 = '9b52bd3d61642838c4348bd8e50cd0a012b7f92c4f7bbab5a1c69824070c96ac'
READ_BEFORE = (b'\x00C\xc1\x81\x02azstr\x00+T\x01aself\x00\x01aSubrecord\x00'
               b'T\x02d\x00l\x01adecode\x00T\x01acp1252\x00')
READ_AFTER = READ_BEFORE.replace(b'cp1252', b'utf-8 ')


def patched_bytes(data: bytes) -> bytes:
    result = data
    for label, old, new in [('source', READ_BEFORE, READ_AFTER),
                            ('output', OUTPUT_CODEC_BEFORE, OUTPUT_CODEC_AFTER),
                            ('FO3 settings', GMST_CODEC_BEFORE, GMST_CODEC_AFTER)]:
        if result.count(old) != 1:
            raise ValueError(f'Unsupported 0.9.148 converter layout: {label}')
        result = result.replace(old, new, 1)
    if len(result) != len(data):
        raise ValueError('Converter patch changed file length')
    return result


def patch_file(source: Path, dest: Path):
    if source.resolve() == dest.resolve() or dest.exists():
        raise ValueError('The original or an existing file cannot be overwritten')
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_SHA256:
        raise ValueError('Unsupported converter SHA-256')
    result = patched_bytes(raw)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('xb') as stream:
        stream.write(result)
    return hashlib.sha256(result).hexdigest()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('dest', type=Path)
    args = parser.parse_args()
    print('Experimental patched copy SHA-256:', patch_file(args.source, args.dest))
