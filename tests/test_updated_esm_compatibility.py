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
            validate_updated_output('fo3',{'text_field_count':1},result,dest,
                                    minimums={'LAND':1,'CELL':1})

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
                validate_updated_output('fo3',{'text_field_count':1},result,dest,
                                        minimums={})

    def test_reused_formid_with_new_editor_id_is_not_translated(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            changed=record(b'MISC',F_ID,'totally_different',[(b'FULL',OLD)])
            src.write_bytes(group(changed))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(src.read_bytes(),dest.read_bytes())
            self.assertEqual(result['unmatched_reasons'],{'editor_id_changed':1})

    def test_duplicate_target_formid_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            old=record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)])
            src.write_bytes(group(old,old))
            plan,edids=translation()
            with self.assertRaisesRegex(ValueError,'Duplicate target record'):
                write_copy(src,dest,plan,edids,allow_changed=True)

    def test_missing_land_rejected_even_when_translation_matches(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);src=root/'Fallout34.esm';dest=root/'mo2.esm'
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',OLD)])))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            with self.assertRaisesRegex(ValueError,'LAND'):
                validate_updated_output('fo3',{'text_field_count':1},result,dest,
                                        minimums={'LAND':1})

    def test_updated_input_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            fo3=root/'Fallout34.esm';nv=root/'FalloutNV34.esm'
            fo3.write_bytes(b'future converter');nv.write_bytes(b'future converter')
            with self.assertRaisesRegex(ValueError,'unsupported'):
                source_preflight(fo3,nv)
            # File-wide SHA requirement can be relaxed only by explicit opt-in.
            manifest,sources=source_preflight(fo3,nv,allow_updated_esms=True)
            self.assertIn('fo3',manifest['games'])
            self.assertEqual(sources['fnv'],nv)


if __name__=='__main__':
    unittest.main()
