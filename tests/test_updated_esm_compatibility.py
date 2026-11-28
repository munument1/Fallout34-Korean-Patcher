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
from build_mo2_korean_mod import validate_updated_output,source_preflight,load_updated_extra,MANIFEST,load_canonical

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
    def test_changed_text_at_same_field_uses_its_own_exact_translation(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'input.esm'
            original=b'Lead\0'
            changed=b'More...\0'
            other=b'More?\0'
            changed_ko='더 보기...'.encode('utf-8')+b'\0'
            plan,edids=translation()
            key=next(iter(plan))
            plan[key]=({hashlib.sha256(original).hexdigest():KO,
                        hashlib.sha256(changed).hexdigest():changed_ko},KO)
            for index,(value,expected) in enumerate(((original,KO),(changed,changed_ko),
                                                       (other,other),(changed_ko,changed_ko))):
                dest=Path(td)/f'out{index}.esm'
                src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',value)])))
                result=write_copy(src,dest,plan,edids,allow_changed=True)
                self.assertIn(expected,dest.read_bytes())
                self.assertEqual(result['unmatched_fields'],int(value==other))

    def test_additional_exact_original_hash_uses_existing_translation(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            other=b'Lead revised\0'
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',other)])))
            plan,edids=translation()
            key=next(iter(plan))
            plan[key]=((hashlib.sha256(OLD).hexdigest(),hashlib.sha256(other).hexdigest()),KO)
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(result['changed_fields'],1)
            self.assertIn(KO,dest.read_bytes())

    def test_updated_extra_data_is_verified_and_distinct_from_base(self):
        import json
        manifest=json.loads(MANIFEST.read_text('utf-8'))
        for game in ('fo3','fnv'):
            meta=manifest['games'][game]
            plan,edids=load_canonical(game,meta)
            before=len(plan)
            rows=json.loads((ROOT/meta['updated_extra_file']).read_text('utf-8'))
            new_count=sum((int(row['id'],16),row['type'],row['field'],row['index']) not in plan for row in rows)
            load_updated_extra(meta,plan,edids)
            self.assertEqual(len(plan)-before,new_count)
            with self.assertRaisesRegex(ValueError,'Invalid updated translation key'):
                load_updated_extra(meta,plan,edids)

    def test_preserves_existing_korean_and_repairs_exact_mojibake_only(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            text='책상 단말기'.encode('utf-8')+b'\0'
            broken=text[:-1].decode('cp1252','replace').encode('utf-8')+b'\0'
            plan={(F_ID,'MISC','FULL',0):(hashlib.sha256(OLD).hexdigest(),text),
                  (F_ID,'MISC','DESC',0):(hashlib.sha256(OLD).hexdigest(),text),
                  (F_ID,'MISC','DESC',1):(hashlib.sha256(OLD).hexdigest(),text)}
            src.write_bytes(group(record(b'MISC',F_ID,'lead_item',[(b'FULL',text),
                (b'DESC',broken),(b'DESC',broken[:-1]+b'!\0')])))
            result=write_copy(src,dest,plan,{(F_ID,'MISC'):'lead_item'},allow_changed=True)
            self.assertEqual(result['already_translated_fields'],1)
            self.assertEqual(result['repaired_mojibake_fields'],1)
            self.assertEqual(result['unmatched_fields'],1)
            self.assertIn(broken[:-1]+b'!\0',dest.read_bytes())
            self.assertEqual(dest.read_bytes().count(text),2)

    def test_mojibake_is_never_repaired_when_editor_id_changed(self):
        with tempfile.TemporaryDirectory() as td:
            src,dest=Path(td)/'input.esm',Path(td)/'output.esm'
            broken=KO[:-1].decode('cp1252','replace').encode('utf-8')+b'\0'
            src.write_bytes(group(record(b'MISC',F_ID,'other_item',[(b'FULL',broken)])))
            plan,edids=translation()
            result=write_copy(src,dest,plan,edids,allow_changed=True)
            self.assertEqual(result['repaired_mojibake_fields'],0)
            self.assertEqual(src.read_bytes(),dest.read_bytes())

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
