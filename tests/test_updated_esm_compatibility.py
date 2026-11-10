"""New converter layouts must preserve existing translations and terrain safely."""
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))

from runtime_esm_writer import HEADER,FIELD,write_copy,inspect_structure
from build_mo2_korean_mod import validate_updated_output,source_preflight

F_ID=0x01010203
OLD=b'Lead\0'
KO='납'.encode('utf-8')+b'\0'


def record(tag:bytes,fid:int,edid:str='',fields=None)->bytes:
    fields=fields or []
    payload=b''
    if edid:
        identifier=edid.encode('ascii')+b'\0'
        payload+=FIELD.pack(b'EDID',len(identifier))+identifier
    for name,value in fields:
        payload+=FIELD.pack(name,len(value))+value
    return HEADER.pack(tag,len(payload),0,fid,0,0)+payload


def group(*records:bytes)->bytes:
    payload=b''.join(records)
    return HEADER.pack(b'GRUP',24+len(payload),0,0,0,0)+payload


def translation():
    return ({(F_ID,'MISC','FULL',0):
             (hashlib.sha256(OLD).hexdigest(),KO)},
            {(F_ID,'MISC'):'lead_item'})


class UpdatedConverterCompatibility(unittest.TestCase):
    def test_47485_land_records_are_preserved_despite_47507_reference(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            land=record(b'LAND',0x01010405,fields=[(b'DATA',b'land')])
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)]),
                                  *(land for _ in range(47485))))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            validate_updated_output('fo3',{'text_field_count':1},result,dest)
            self.assertEqual(result['record_type_counts']['LAND'],47485)
            self.assertEqual(inspect_structure(src)['land_sha256'],
                             inspect_structure(dest)['land_sha256'])

    def test_partial_matches_translate_without_99_percent_cutoff(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',
                             [(b'FULL',OLD),(b'DESC',b'Changed description\0')]),
                             record(b'LAND',123,fields=[(b'DATA',b'land')])))
            plan,edids=translation()
            plan[(F_ID,'MISC','DESC',0)]=(hashlib.sha256(b'Old description\0').hexdigest(),KO)
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            validate_updated_output('fo3',{'text_field_count':2},result,dest)
            self.assertEqual(result['changed_fields'],1)
            self.assertEqual(result['unmatched_fields'],1)
            self.assertIn(b'Changed description\0',dest.read_bytes())

    def test_changed_land_bytes_rejected_even_when_record_counts_match(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)]),
                                  record(b'LAND',123,fields=[(b'DATA',b'land')])))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            dest.write_bytes(dest.read_bytes().replace(b'land',b'FAIL'))
            with self.assertRaisesRegex(ValueError,'LAND bytes'):
                validate_updated_output('fo3',{'text_field_count':1},result,dest)

    def test_add_records_reuses_old_korean_and_preserves_new_english_and_land(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            old=record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)])
            new=record(b'MISC',0x01010204,'new_item',[(b'FULL',b'New content\0')])
            land=record(b'LAND',0x01010405,fields=[(b'DATA',bytes(range(8)))])
            cell=record(b'CELL',0x01010406)
            src.write_bytes(group(old,new,land,cell))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            output=dest.read_bytes()
            self.assertEqual(result['changed_fields'],1)
            self.assertEqual(result['unmatched_fields'],0)
            self.assertIn(KO,output)
            self.assertIn(new,output)
            self.assertIn(land,output)
            self.assertEqual(inspect_structure(dest)['records'],4)
            validate_updated_output('fo3',{'text_field_count':1},result,dest)

    def test_modified_original_is_not_overwritten_and_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            old=record(b'MISC',F_ID,'lead_item',[(b'FULL',b'Lead changed\0')])
            src.write_bytes(group(old))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(dest.read_bytes(),src.read_bytes())
            self.assertEqual(result['unmatched_reasons'],{'original_text_changed':1})
            with self.assertRaisesRegex(ValueError,'matched'):
                validate_updated_output('fo3',{'text_field_count':1},result,dest)

    def test_reused_formid_with_new_editor_id_is_not_translated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            changed=record(b'MISC',F_ID,'totally_different',[(b'FULL',OLD)])
            src.write_bytes(group(changed))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(src.read_bytes(),dest.read_bytes())
            self.assertEqual(result['unmatched_reasons'],{'editor_id_changed':1})

    def test_duplicate_targets_are_translated_independently(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            old=record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)])
            src.write_bytes(group(old,old))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(result['changed_fields'],2)
            self.assertEqual(result['unmatched_fields'],0)
            self.assertEqual(result['duplicate_target_records'],1)
            self.assertEqual(dest.read_bytes().count(KO),2)

    def test_duplicate_target_with_different_text_is_preserved_and_reported(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            good=record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)])
            changed=record(b'MISC',F_ID,'lead_item',[(b'FULL',b'Changed lead\0')])
            src.write_bytes(group(good,changed))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(result['changed_fields'],1)
            self.assertEqual(result['unmatched_fields'],0)
            self.assertEqual(result['skipped_occurrence_reasons'],{'original_text_changed':1})
            self.assertIn(changed,dest.read_bytes())

    def test_input_without_land_can_translate_and_preserves_its_structure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)])))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            validate_updated_output('fo3',{'text_field_count':1},result,dest)
            self.assertEqual(inspect_structure(dest)['record_type_counts'],{'MISC':1})

    def test_updated_input_is_automatic_but_internal_strict_check_remains_available(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fo3=root/'Fallout34.esm';nv=root/'FalloutNV34.esm'
            fo3.write_bytes(b'future converter');nv.write_bytes(b'future converter')
            with self.assertRaisesRegex(ValueError,'unsupported'):
                source_preflight(fo3,nv,allow_updated_esms=False)
            # GUI and CLI use automatic per-field matching by default.
            manifest,sources=source_preflight(fo3,nv)
            self.assertIn('fo3',manifest['games'])
            self.assertEqual(sources['fnv'],nv)


if __name__=='__main__':
    unittest.main()
