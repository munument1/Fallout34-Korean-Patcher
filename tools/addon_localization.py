"""Translate supported optional Fallout 34 add-ons without modifying their originals."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import zlib

from runtime_esm_writer import FIELD, HEADER, inspect_structure, sha256, write_copy
from atomic_shop_translation import translate_swf

DISPLAY_KEYS = {'displayName', 'pageDisplayName', 'text', 'help'}
CONFIGS = ('Fallout34', 'F34_Settlements', 'F34_NVSS', 'F34_KARMA', 'F34_MojavePatrols')


def verify_addon_data(data_dir: Path, manifest: dict):
    hashes = manifest.get('addon_data_sha256', {})
    if set(hashes) != {'settlement-names.json', 'settlement-records.json', 'mcm-translations.json', 'atomic-shop-09148.json', 'atomic-bundles.json', 'atomic-items.json'}:
        raise ValueError('Optional add-on translation manifest is incomplete')
    for filename, expected in hashes.items():
        if sha256(data_dir / filename) != expected:
            raise ValueError(f'Optional add-on translation data altered: {filename}')


def _subrecords(raw: bytes):
    offset = 0
    counts = Counter()
    while offset < len(raw):
        if offset + 6 > len(raw):
            raise ValueError('Truncated add-on subrecord')
        tag, size = FIELD.unpack_from(raw, offset)
        offset += 6
        if tag == b'XXXX':
            if size != 4 or offset + 10 > len(raw):
                raise ValueError('Invalid add-on extended subrecord')
            size = struct.unpack_from('<I', raw, offset)[0]
            offset += 4
            tag, _ = FIELD.unpack_from(raw, offset)
            offset += 6
        if offset + size > len(raw):
            raise ValueError('Add-on subrecord exceeds record')
        index = counts[tag]
        counts[tag] += 1
        yield tag, index, raw[offset:offset + size]
        offset += size


def _find(roots: list[Path], relative: Path):
    found = []
    for root in roots:
        candidate = root / relative
        if candidate.is_file() and candidate.resolve() not in found:
            found.append(candidate.resolve())
    return found


def _roots(source_dir: Path, addon_dir: Path | None):
    roots = [source_dir]
    if addon_dir:
        if not addon_dir.is_dir():
            raise ValueError('추가 모드 폴더가 존재하지 않습니다')
        roots.append(addon_dir)
        # Selecting MO2's mods directory includes each immediate mod folder.
        if addon_dir.name.casefold() == 'mods':
            roots.extend(p for p in addon_dir.iterdir() if p.is_dir() and not p.is_symlink())
    return roots


def _single(candidates, label, result):
    if len(candidates) > 1:
        result['ambiguous'].append(label)
        return None
    return candidates[0] if candidates else None


def _settlement_plan(source: Path, rows: list[dict]):
    lookup = {(r.get('type', 'LCTN'), r['edid'].casefold()): r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError('Duplicate settlement translation EditorID')
    plan, ids, seen_edids = {}, {}, set()
    skipped = []
    with source.open('rb') as stream:
        total = source.stat().st_size
        pos = 0
        own_index = None
        masters = []
        while pos < total:
            header = stream.read(24)
            if len(header) != 24:
                raise ValueError('Truncated add-on record header')
            tag, size, flags, fid, *_ = HEADER.unpack(header)
            if tag == b'GRUP':
                pos += 24
                continue
            if size > 64 * 1024 * 1024 or pos + 24 + size > total:
                raise ValueError('Invalid add-on record size')
            raw = stream.read(size)
            pos += 24 + size
            if tag not in (b'TES4', b'LCTN', b'CELL', b'QUST', b'KYWD', b'FLST', b'FACT'):
                continue
            if flags & 0x40000:
                if len(raw) < 4:
                    raise ValueError('Invalid compressed add-on record')
                expected = struct.unpack_from('<I', raw)[0]
                raw = zlib.decompress(raw[4:])
                if len(raw) != expected:
                    raise ValueError('Invalid compressed add-on size')
            fields = list(_subrecords(raw))
            if tag == b'TES4':
                if own_index is not None or flags & 0x80:
                    raise ValueError('Unsupported localized or duplicate add-on header')
                masters = [v.rstrip(b'\0').decode('ascii', 'strict').casefold()
                           for t, _, v in fields if t == b'MAST']
                if len(set(masters)) != len(masters):
                    raise ValueError('Duplicate add-on master')
                own_index = len(masters)
                continue
            if own_index is None:
                raise ValueError('Add-on header must precede records')
            edids = [v.rstrip(b'\0').decode('ascii', 'strict').casefold()
                     for t, _, v in fields if t == b'EDID']
            typ = tag.decode('ascii')
            if len(edids) != 1 or (typ, edids[0]) not in lookup:
                continue
            edid = edids[0]
            recordkey = (typ, edid)
            if recordkey in seen_edids:
                raise ValueError(f'Duplicate settlement EditorID: {edid}')
            seen_edids.add(recordkey)
            row = lookup[recordkey]
            full = [(index, value) for t, index, value in fields if t == b'FULL']
            if len(full) != 1:
                skipped.append(edid)
                continue
            ix, original = full[0]
            korean = row['korean'].encode('utf8') + b'\0'
            if row.get('source_master'):
                master = row['source_master'].casefold()
                if (master not in masters or fid >> 24 != masters.index(master) or
                        fid & 0xFFFFFF != int(row['source_id'], 16)):
                    skipped.append(edid)
                    continue
                if original == korean:
                    continue
                if hashlib.sha256(original).hexdigest() != row['before_sha256']:
                    skipped.append(edid)
                    continue
            elif fid >> 24 != own_index or original != row['english'].encode('cp1252') + b'\0':
                skipped.append(edid)
                continue
            key = (fid, typ, 'FULL', ix)
            plan[key] = (hashlib.sha256(original).hexdigest(), korean)
            ids[(fid, typ)] = edid
    return plan, ids, skipped


def _translate_config(source: Path, dest: Path, translations: dict):
    original_hash = sha256(source)
    doc = json.loads(source.read_text(encoding='utf-8-sig'))
    replaced = 0
    unknown = set()

    def visit(node):
        nonlocal replaced
        if isinstance(node, list):
            for child in node:
                visit(child)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key == 'options' and isinstance(value, list) and all(isinstance(v, str) for v in value):
                    for index, option in enumerate(value):
                        if option in translations:
                            value[index] = translations[option]
                            replaced += 1
                        elif option and not any('\uac00' <= c <= '\ud7a3' for c in option):
                            unknown.add(option)
                elif key in DISPLAY_KEYS and isinstance(value, str):
                    if value in translations:
                        node[key] = translations[value]
                        replaced += 1
                    elif value and not any('\uac00' <= c <= '\ud7a3' for c in value):
                        unknown.add(value)
                else:
                    visit(value)

    visit(doc)
    if sha256(source) != original_hash:
        raise ValueError('MCM source changed during processing')
    if replaced:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return {'translated_fields': replaced, 'unmatched_strings': sorted(unknown)}


def _translate_bundles(source: Path, dest: Path, translations: dict):
    original_hash = sha256(source)
    lines = source.read_text(encoding='utf-8-sig').splitlines(keepends=True)
    replaced, unknown = 0, []
    output = []
    for line in lines:
        fields = line.split('|', 4)
        if len(fields) != 5:
            if line.strip():
                unknown.append('malformed line')
            output.append(line)
            continue
        key, english = fields[0], fields[1]
        if key in translations and english == translations[key][0]:
            fields[1] = translations[key][1]
            replaced += 1
        else:
            unknown.append(key)
        output.append('|'.join(fields))
    if sha256(source) != original_hash:
        raise ValueError('Atomic Shop bundles changed during processing')
    if replaced:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(''.join(output), encoding='utf8', newline='')
    return {'translated_names': replaced, 'unmatched_keys': sorted(set(unknown))}


def _translate_items(source: Path, dest: Path, rows: list[dict]):
    translations = {str(row['id']): row for row in rows}
    if len(translations) != len(rows):
        raise ValueError('Duplicate Atomic Shop item ID')
    original = source.read_bytes()
    # Generated names can contain C1 controls from a Latin-1/UTF-8 mix-up;
    # only LF is a row separator, not Python's broader splitlines set.
    lines = original.decode('utf8').split('\n')
    result = []
    replaced = 0
    unmatched = 0
    for index, line in enumerate(lines):
        if index == len(lines)-1 and not line:
            continue
        content = line.removesuffix('\r')
        ending = ('\r' if line.endswith('\r') else '') + ('\n' if index < len(lines)-1 else '')
        parts = content.split('|', 6)
        if len(parts) != 7:
            if content:
                unmatched += 1
            result.append(content + ending)
            continue
        row = translations.get(parts[0])
        if (row and parts[1] == row['category'] and parts[2] == row['type'] and
                hashlib.sha256(parts[6].encode('utf8')).hexdigest() == row['before_sha256']):
            parts[6] = row['korean']
            replaced += 1
        elif parts[6] and not any('\uac00' <= c <= '\ud7a3' for c in parts[6]):
            unmatched += 1
        result.append('|'.join(parts) + ending)
    if source.read_bytes() != original:
        raise ValueError('Atomic Shop item list changed during processing')
    if replaced:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(''.join(result).encode('utf8'))
    return {'translated_names': replaced, 'unmatched_names': unmatched}


def translate_addons(source_dir: Path, addon_dir: Path | None, output: Path, data_dir: Path):
    roots = _roots(source_dir, addon_dir)
    result = {'ambiguous': [], 'settlements': None, 'mcm': {}, 'atomic_shop': None, 'bundles': None, 'items': None}
    source = _single(_find(roots, Path('F34_Settlements.esp')), 'F34_Settlements.esp', result)
    if source:
        source_hash = sha256(source)
        rows = (json.loads((data_dir / 'settlement-names.json').read_text(encoding='utf8')) +
                json.loads((data_dir / 'settlement-records.json').read_text(encoding='utf8')))
        plan, ids, skipped = _settlement_plan(source, rows)
        names = sum(key[1] == 'LCTN' for key in plan)
        result['settlements'] = {'matched_names': names, 'matched_other_fields': len(plan) - names, 'changed_names': skipped}
        if plan:
            dest = output / 'F34_Settlements.esp'
            written = write_copy(source, dest, plan, ids, allow_changed=False)
            before, after = inspect_structure(source), inspect_structure(dest)
            if (before['records'], before['groups'], before['record_type_counts'], before['land_sha256']) != (
                    after['records'], after['groups'], after['record_type_counts'], after['land_sha256']):
                raise ValueError('Settlement add-on structure changed')
            if written['changed_fields'] != len(plan) or sha256(source) != source_hash:
                raise ValueError('Settlement add-on translation verification failed')
    translations = json.loads((data_dir / 'mcm-translations.json').read_text(encoding='utf8'))
    for name in CONFIGS:
        relative = Path('MCM') / 'Config' / name / 'config.json'
        source = _single(_find(roots, relative), str(relative), result)
        if source:
            result['mcm'][name] = _translate_config(source, output / relative, translations)
    relative = Path('Interface') / 'F34Settlements' / 'AtomicShop.swf'
    source = _single(_find(roots, relative), str(relative), result)
    if source:
        rules = json.loads((data_dir / 'atomic-shop-09148.json').read_text(encoding='utf8'))
        original_hash = sha256(source)
        if original_hash != rules['source_sha256']:
            result['atomic_shop'] = {'status': 'different_version'}
        else:
            translated = translate_swf(source.read_bytes(), rules['strings'])
            if sha256(source) != original_hash:
                raise ValueError('Atomic Shop source changed during processing')
            dest = output / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(translated)
            result['atomic_shop'] = {'status': 'translated', 'translated_strings': len(rules['strings'])}
    relative = Path('Interface') / 'F34Settlements' / 'AtomicShop' / 'bundles.txt'
    source = _single(_find(roots, relative), str(relative), result)
    if source:
        translations = json.loads((data_dir / 'atomic-bundles.json').read_text(encoding='utf8'))
        result['bundles'] = _translate_bundles(source, output / relative, translations)
    relative = Path('Interface') / 'F34Settlements' / 'AtomicShop' / 'items.txt'
    source = _single(_find(roots, relative), str(relative), result)
    if source:
        rows = json.loads((data_dir / 'atomic-items.json').read_text(encoding='utf8'))
        result['items'] = _translate_items(source, output / relative, rows)
    return result
