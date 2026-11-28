"""Create a local *experimental* UTF-8-aware copy of Fallout34 0.9.102.

The upstream converter is distributed as a compiled Nuitka executable.
This narrowly patches the compiled string constants used by:
- f34.esm.Subrecord.zstr: decoding text from source ESMs
- f34.ctx.zstr: encoding string subrecords for the FO4 ESM output
- f34.systems.fo3_settings: reading string game settings
These are the common source and destination helpers. It does not patch
unrelated CP1252 reads/writes and is not an upstream UTF-8/CP1252
fallback implementation.

Do not distribute the patched executable; this is for the installer's
owner to test with their own copy.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


VERSION = "0.9.102"
ORIGINAL_SHA256 = "ecc007ed6531c0048fbbe377b70d60b3fc3697c293303ef03ed09a835cb59025"

# Nuitka serializes the function's constant table in this executable.
# This exact context uniquely selects f34.esm.Subrecord.zstr (line 27).
# The 6-character codec alias "utf-8 " resolves to UTF-8 in Python, so
# the replacement is exactly the same size as "cp1252".
READ_ANCHOR = (
    b"\x00C\xc1\x81\x02azstr\x00\x1aT\x01aself\x00\x01aSubrecord\x00"
    b"T\x02d\x00l\x01adecode\x00T\x01a"
)
WRITE_ANCHOR = (
    b"\x00C\xc0\x81\x02azstr\x00_T\x01ws\x01aencode\x00T\x02a"
)
SOURCE_CODEC_BEFORE = READ_ANCHOR + b"cp1252\x00"
SOURCE_CODEC_AFTER = READ_ANCHOR + b"utf-8 \x00"
OUTPUT_CODEC_BEFORE = WRITE_ANCHOR + b"cp1252\x00areplace\x00"
OUTPUT_CODEC_AFTER = WRITE_ANCHOR + b"utf-8 \x00areplace\x00"
GMST_CODEC_BEFORE = b"\x00d\x00l\x80\x04adecode\x00T\x01acp1252\x00C\xc0\x81\x02afo3_settings\x00"
GMST_CODEC_AFTER = GMST_CODEC_BEFORE.replace(b"cp1252", b"utf-8 ")


def patched_bytes(original: bytes) -> bytes:
    patches = (
        ("f34.esm.Subrecord.zstr", SOURCE_CODEC_BEFORE, SOURCE_CODEC_AFTER),
        ("f34.ctx.zstr", OUTPUT_CODEC_BEFORE, OUTPUT_CODEC_AFTER),
        ("f34.systems.fo3_settings", GMST_CODEC_BEFORE, GMST_CODEC_AFTER),
    )
    for label, old, _ in patches:
        count = original.count(old)
        if count != 1:
            raise ValueError(
                f"Unsupported converter binary: expected one {label} CP1252 constant, "
                f"found {count}"
            )
    result = original
    for _, old, new in patches:
        result = result.replace(old, new, 1)
    if len(result) != len(original):
        raise AssertionError("Patching must preserve the executable's length")
    return result


def patch_file(source: Path, target: Path) -> tuple[str, str]:
    if source.resolve() == target.resolve():
        raise ValueError("The converter must be copied; the original cannot be overwritten")
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite: {target}")
    raw = source.read_bytes()
    original_hash = hashlib.sha256(raw).hexdigest()
    if original_hash != ORIGINAL_SHA256:
        raise ValueError(
            f"Expected unmodified Fallout34 {VERSION} f34conv.exe "
            f"({ORIGINAL_SHA256}); got {original_hash}"
        )
    output = patched_bytes(raw)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(output)
    return original_hash, hashlib.sha256(output).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Original payload/app/f34conv.exe")
    parser.add_argument("target", type=Path, help="New, distinct path for patched f34conv.exe")
    args = parser.parse_args()
    old, new = patch_file(args.source, args.target)
    print(f"Fallout34 {VERSION} source/output zstr UTF-8 trial patched")
    print(f"Source SHA-256: {old}")
    print(f"Output SHA-256: {new}")
    print(f"Created: {args.target}")
    print("WARNING: Native CP1252-only names may fail to decode; full conversion is unverified.")


if __name__ == "__main__":
    main()
