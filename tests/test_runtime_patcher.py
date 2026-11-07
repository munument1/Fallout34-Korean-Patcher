"""Regression tests for new terrain-preserving, canonical-only MO2 patcher."""
from __future__ import annotations
import hashlib,json,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))

from runtime_esm_writer import HEADER,FIELD,write_copy,sha256
from build_mo2_korean_mod import load_canonical,verify_directory_safety,source_preflight
from fo4_korean_assets import select_assets
from audit_fo4_swf_glyphs import parse_swf


class SafeRuntimePatcher(unittest.TestCase):
    def test_canonical_manifest_only_hashes_no_english_original(self):
        manifest=json.loads((ROOT/'data'/'canonical'/'manifest.json').read_text('utf-8'))
        self.assertEqual(manifest['schema'],2)
        self.assertEqual(sum(item['text_field_count'] for item in manifest['games'].values()),321328)
        for game,meta in manifest['games'].items():
            plan,editor_ids=load_canonical(game,meta)
            self.assertEqual(len(plan),meta['text_field_count'])
            self.assertTrue(editor_ids)
            one=next(iter(plan.values()))
            self.assertEqual(len(one[0]),64)
            self.assertTrue(any(ord(x)>127 for x in one[1].decode('utf-8')))

    def test_fo4_assets_and_font_glyphs(self):
        chosen=select_assets()
        self.assertEqual(chosen['asset_count'],505)
        self.assertEqual(chosen['conflicting_en_ko_cc_variants_kept_en'],33)
        expected={'Interface/fonts_en.swf':7,
                  'Interface/fonts_console.swf':2,
                  'Programs/fonts_programs.swf':4}
        for rel,num in expected.items():
            data=parse_swf(ROOT/'assets'/'fo4_korean'/rel)
            fonts=[f for f in data['font_tags'] if f.get('korean_syllable_glyphs')==11172]
            self.assertEqual(len(fonts),num,f'Full Hangul glyph count mismatch {rel}')

    def test_writer_changes_only_expected_utf8_text_and_group_size(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            frm=tmp/'Fallout34.esm';to=tmp/'localized.esm'
            eid=b'test_item\0';before=b'Lead\0';after='납'.encode('utf-8')+b'\0'
            rec_payload=FIELD.pack(b'EDID',len(eid))+eid+FIELD.pack(b'FULL',len(before))+before
            item=HEADER.pack(b'MISC',len(rec_payload),0,0x01010203,123,456)+rec_payload
            land_blob=FIELD.pack(b'DATA',8)+bytes(range(8))
            land=HEADER.pack(b'LAND',len(land_blob),0,0x01020304,0,0)+land_blob
            grp=HEADER.pack(b'GRUP',24+len(item)+len(land),0,0,0,0)+item+land
            frm.write_bytes(grp)
            plan={(0x01010203,'MISC','FULL',0):(hashlib.sha256(before).hexdigest(),after)}
            ids={(0x01010203,'MISC'):'test_item'}
            report=write_copy(frm,to,plan,ids)
            self.assertEqual(report['changed_fields'],1)
            self.assertEqual(report['groups'],1)
            self.assertEqual(report['records'],2)
            output=to.read_bytes()
            self.assertIn(after,output)
            self.assertEqual(output[-len(land):],land,'LAND bytes must be unchanged')
            self.assertEqual(int.from_bytes(output[4:8],'little'),len(output))
            with self.assertRaises(ValueError):write_copy(frm,to,plan,ids)

    def test_writer_rejects_wrong_edid_and_mismatched_original(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'a.esm';out=root/'b.esm'
            edid=b'expected_id\0';original=b'Wrong\0';new='정상'.encode('utf-8')+b'\0'
            blob=FIELD.pack(b'EDID',len(edid))+edid+FIELD.pack(b'FULL',len(original))+original
            src.write_bytes(HEADER.pack(b'MISC',len(blob),0,0x01010000,0,0)+blob)
            plan={(0x01010000,'MISC','FULL',0):(hashlib.sha256(original).hexdigest(),new)}
            with self.assertRaisesRegex(ValueError,'EditorID'):
                write_copy(src,out,plan,{(0x01010000,'MISC'):'different_editorid'})
            out.unlink()
            bad={(0x01010000,'MISC','FULL',0):('0'*64,new)}
            with self.assertRaisesRegex(ValueError,'alignment'):
                write_copy(src,out,bad,{(0x01010000,'MISC'):'expected_id'})

    def test_wrong_converter_sha_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);fo3=root/'Fallout34.esm';nv=root/'FalloutNV34.esm'
            fo3.write_bytes(b'not the right conversion');nv.write_bytes(b'invalid')
            with self.assertRaisesRegex(ValueError,'unsupported'):
                source_preflight(fo3,nv)
            with self.assertRaises(ValueError):
                verify_directory_safety({'fo3':fo3,'fnv':nv},root/'inside-source')


if __name__=='__main__':unittest.main()
