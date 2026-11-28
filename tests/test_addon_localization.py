import json
import hashlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from addon_localization import translate_addons, _subrecords, _translate_bundles, _translate_items, _settlement_plan
from atomic_shop_translation import translate_swf, _unpack_swf
from runtime_esm_writer import FIELD, HEADER, inspect_structure


def sub(tag, value):
    return FIELD.pack(tag, len(value)) + value


def record(tag, fid, fields, flags=0):
    raw = b''.join(fields)
    if flags & 0x40000:
        raw = struct.pack('<I', len(raw)) + zlib.compress(raw)
    return HEADER.pack(tag, len(raw), flags, fid, 0, 0) + raw


def group(tag, records):
    raw = b''.join(records)
    return HEADER.pack(b'GRUP', len(raw)+24, int.from_bytes(tag, 'little'), 0, 0, 0) + raw


def plugin(names, header_flags=0):
    masters = [sub(b'MAST', x.encode('ascii')+b'\0') + sub(b'DATA', bytes(8))
               for x in ('Fallout4.esm', 'Fallout34.esm', 'FalloutNV34.esm', 'WorkshopFramework.esm')]
    header = record(b'TES4', 0, masters, header_flags)
    records = [record(b'LCTN', 0x04001000+i,
                      [sub(b'EDID', edid.encode('ascii')+b'\0'), sub(b'FULL', value.encode('ascii')+b'\0'),
                       sub(b'KSIZ', struct.pack('<I', 3))], 0x40000 if i == 0 else 0)
               for i, (edid, value) in enumerate(names)]
    return header + group(b'LCTN', records)


class AddonLocalizationTests(unittest.TestCase):
    def test_shop_item_names_require_id_category_type_and_original_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'items.txt'
            dest = root/'out.txt'
            source.write_text('1|FO3|Decor|100|F01|pic|Street Light 2\n2|FO3|Decor|10|F02|pic|Changed\n', encoding='utf8')
            row = {'id': 1, 'category': 'FO3', 'type': 'Decor',
                   'before_sha256': hashlib.sha256(b'Street Light 2').hexdigest(), 'korean': '거리 조명 2'}
            report = _translate_items(source, dest, [row])
            self.assertEqual(report, {'translated_names': 1, 'unmatched_names': 1})
            self.assertEqual(dest.read_text('utf8'), '1|FO3|Decor|100|F01|pic|거리 조명 2\n2|FO3|Decor|10|F02|pic|Changed\n')

    def test_shop_item_latin1_mojibake_c1_controls_are_not_row_breaks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, dest = root/'items.txt', root/'out.txt'
            broken = '침대'.encode('utf8').decode('latin1')
            source.write_bytes(f'1|FO3|Furniture|100|F01|pic|{broken}\r\n'.encode('utf8'))
            row = {'id': 1, 'category': 'FO3', 'type': 'Furniture',
                   'before_sha256': hashlib.sha256(broken.encode('utf8')).hexdigest(), 'korean': '침대'}
            self.assertEqual(_translate_items(source, dest, [row])['translated_names'], 1)
            self.assertEqual(dest.read_bytes(), '1|FO3|Furniture|100|F01|pic|침대\r\n'.encode('utf8'))
    def test_bundle_translation_preserves_ids_prices_and_changed_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'in.txt'
            dest = root/'out.txt'
            source.write_text('robots|Robot Clutter|20|bundle_robots|1,2,3\ntrash|Changed name|20|p|4,5,6\n', encoding='utf8')
            translations = json.loads((ROOT/'data'/'atomic-bundles.json').read_text(encoding='utf8'))
            report = _translate_bundles(source, dest, translations)
            self.assertEqual(report['translated_names'], 1)
            self.assertEqual(report['unmatched_keys'], ['trash'])
            self.assertEqual(dest.read_text(encoding='utf8'), 'robots|로봇 잡동사니|20|bundle_robots|1,2,3\ntrash|Changed name|20|p|4,5,6\n')

    def test_swf_patch_changes_only_reviewed_string_pool_and_round_trips(self):
        abc = struct.pack('<HH', 16, 46) + b'\0\0\0\x02\x03BUY' + b'unchanged-bytecode'
        doabc = bytes(4) + b'\0' + abc
        body = b'\x08\0' + struct.pack('<HH', 30 << 8, 1)
        body += struct.pack('<HI', 82 << 6 | 63, len(doabc)) + doabc
        body += struct.pack('<H', 0)
        source = b'FWS\x0f' + struct.pack('<I', len(body)+8) + body
        translated = translate_swf(source, {'BUY': '구매'})
        self.assertIn('구매'.encode('utf8'), _unpack_swf(translated))
        self.assertIn(b'unchanged-bytecode', _unpack_swf(translated))
        with self.assertRaises(ValueError):
            translate_swf(source, {'OTHER': '다른 항목'})

    def test_all_known_settlement_names_are_written(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = json.loads((ROOT/'data'/'settlement-names.json').read_text(encoding='utf8'))
            original = plugin([(r['edid'], r['english']) for r in rows])
            (root/'F34_Settlements.esp').write_bytes(original)
            out = root/'out'
            out.mkdir()
            report = translate_addons(root, None, out, ROOT/'data')
            self.assertEqual(report['settlements']['matched_names'], 48)
            payload = (out/'F34_Settlements.esp').read_bytes()
            found = {}
            pos = 0
            while pos < len(payload):
                typ, size, flags, _, _, _ = HEADER.unpack_from(payload, pos)
                if typ == b'GRUP':
                    pos += 24
                    continue
                raw = payload[pos+24:pos+24+size]
                pos += 24+size
                if typ != b'LCTN':
                    continue
                if flags & 0x40000:
                    raw = zlib.decompress(raw[4:])
                values = {t: v for t, _, v in _subrecords(raw)}
                found[values[b'EDID'].rstrip(b'\0').decode('ascii')] = values[b'FULL'].rstrip(b'\0').decode('utf8')
            self.assertEqual(found, {r['edid']: r['korean'] for r in rows})
            self.assertEqual((root/'F34_Settlements.esp').read_bytes(), original)

    def test_settlement_workshop_menu_names_are_translated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            quest = record(b'QUST', 0x04002000,
                           [sub(b'EDID', b'F34S_AtomicShop\0'), sub(b'FULL', b'Atomic Shop\0')])
            (root/'F34_Settlements.esp').write_bytes(plugin([]) + group(b'QUST', [quest]))
            out = root/'out'
            out.mkdir()
            report = translate_addons(root, None, out, ROOT/'data')
            self.assertEqual(report['settlements']['matched_other_fields'], 1)
            self.assertIn('아토믹 상점'.encode('utf8') + b'\0', (out/'F34_Settlements.esp').read_bytes())

    def test_overridden_cell_requires_original_master_form_and_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            value = b'Bridge\0'
            cell = record(b'CELL', 0x01001234,
                          [sub(b'EDID', b'F3_DLC05Bridge\0'), sub(b'FULL', value)])
            source = root/'F34_Settlements.esp'
            source.write_bytes(plugin([]) + group(b'CELL', [cell]))
            row = {'type': 'CELL', 'edid': 'f3_dlc05bridge', 'source_master': 'Fallout34.esm',
                   'source_id': '001234', 'before_sha256': hashlib.sha256(value).hexdigest(), 'korean': '함교'}
            plan, _, skipped = _settlement_plan(source, [row])
            self.assertEqual(len(plan), 1)
            self.assertEqual(skipped, [])
            row['source_master'] = 'FalloutNV34.esm'
            plan, _, skipped = _settlement_plan(source, [row])
            self.assertFalse(plan)
            self.assertEqual(skipped, ['f3_dlc05bridge'])

    def test_optional_mods_use_exact_identity_and_translate_display_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base/'mods'/'Settlement'
            source.mkdir(parents=True)
            esp = source/'F34_Settlements.esp'
            esp.write_bytes(plugin([('F34S_SpringvaleLocation', 'Springvale'),
                                    ('F34S_GoodspringsLocation', 'Different new text')]))
            original = esp.read_bytes()
            config = source/'MCM'/'Config'/'F34_Settlements'/'config.json'
            config.parent.mkdir(parents=True)
            config.write_text(json.dumps({'displayName': 'Fallout 34 Settlements',
                                          'pluginRequirements': ['F34_Settlements.esp'],
                                          'content': [{'text': 'Open the Atomic Shop',
                                                       'action': {'form': 'F34_Settlements.esp|F1000'}}]}), encoding='utf8')
            out = base/'result'
            out.mkdir()
            report = translate_addons(base, base/'mods', out, ROOT/'data')
            self.assertEqual(report['settlements']['matched_names'], 1)
            self.assertEqual(report['settlements']['changed_names'], ['f34s_goodspringslocation'])
            self.assertEqual(report['mcm']['F34_Settlements']['translated_fields'], 2)
            self.assertEqual(esp.read_bytes(), original)
            target = out/'F34_Settlements.esp'
            self.assertEqual(inspect_structure(esp)['record_type_counts'], inspect_structure(target)['record_type_counts'])
            self.assertIn(b'Different new text\0', target.read_bytes())
            changed = json.loads((out/'MCM'/'Config'/'F34_Settlements'/'config.json').read_text(encoding='utf8'))
            self.assertEqual(changed['content'][0]['text'], '아토믹 상점 열기')
            self.assertEqual(changed['content'][0]['action']['form'], 'F34_Settlements.esp|F1000')

    def test_rejects_localized_plugin_and_duplicate_editor_ids(self):
        for data in (plugin([('F34S_SpringvaleLocation', 'Springvale')], 0x80),
                     plugin([('F34S_SpringvaleLocation', 'Springvale'),
                             ('F34S_SpringvaleLocation', 'Springvale')])):
            with self.subTest(size=len(data)), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                (root/'F34_Settlements.esp').write_bytes(data)
                out = root/'out'
                out.mkdir()
                with self.assertRaises(ValueError):
                    translate_addons(root, None, out, ROOT/'data')

    def test_ambiguous_files_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mods = root/'mods'
            for name in ('one', 'two'):
                (mods/name).mkdir(parents=True)
                (mods/name/'F34_Settlements.esp').write_bytes(plugin([('F34S_SpringvaleLocation', 'Springvale')]))
            out = root/'out'
            out.mkdir()
            report = translate_addons(root, mods, out, ROOT/'data')
            self.assertEqual(report['ambiguous'], ['F34_Settlements.esp'])
            self.assertFalse((out/'F34_Settlements.esp').exists())

    def test_unknown_atomic_shop_version_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'Interface'/'F34Settlements'/'AtomicShop.swf'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'future version')
            out = root/'out'
            out.mkdir()
            report = translate_addons(root, None, out, ROOT/'data')
            self.assertEqual(report['atomic_shop']['status'], 'different_version')
            self.assertFalse((out/'Interface'/'F34Settlements'/'AtomicShop.swf').exists())
            self.assertEqual(source.read_bytes(), b'future version')

    def test_dropdown_labels_translate_without_changing_values(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/'MCM'/'Config'/'F34_MojavePatrols'/'config.json'
            source.parent.mkdir(parents=True)
            config = {'content': [{'text': 'How often', 'valueOptions': {'sourceType': 'GlobalValue',
                        'sourceForm': 'F34_MojavePatrols.esp|801', 'options': ['Rare', 'Occasional', 'Common']}}]}
            source.write_text(json.dumps(config), encoding='utf8')
            out = root/'out'
            out.mkdir()
            report = translate_addons(root, None, out, ROOT/'data')
            self.assertEqual(report['mcm']['F34_MojavePatrols']['translated_fields'], 4)
            result = json.loads((out/'MCM'/'Config'/'F34_MojavePatrols'/'config.json').read_text(encoding='utf8'))
            self.assertEqual(result['content'][0]['valueOptions']['options'], ['드묾', '가끔', '자주'])
            self.assertEqual(result['content'][0]['valueOptions']['sourceForm'], 'F34_MojavePatrols.esp|801')


if __name__ == '__main__':
    unittest.main()
