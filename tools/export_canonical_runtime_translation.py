"""Export only portable text-field deltas from verified full-terrain local ESMs.

NEVER export ESMs, LAND/CELL geometry, Bethesda binary record bodies or BA2.
Input is the independently verified FO3/FNV text transfer plan used in the
Fallout34 FULL TERRAIN fix; output is compact gzip JSONL, indexed by FormID,
record type, field tag and occurrence plus exact before/after text-field bytes.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
DEFAULT_INPUT=pathlib.Path(r'D:\Fallout34\mods\KR\QuestionMarks_FullTerrain_Merged_V1')
OUT=ROOT/'data'/'canonical'
SCHEMA=2

def digest(path:pathlib.Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def build(source:pathlib.Path,output:pathlib.Path):
    output.mkdir(parents=True,exist_ok=True)
    manifest={'schema':SCHEMA,'description':'Verified UTF-8 Korean text only, hashed original fields, no game ESM or English source passage',
              'original_field_proof':'sha256(original NUL-terminated field bytes), no English strings are redistributed',
              'games':{}}
    for game,name in (('fo3','Fallout34.esm'),('fnv','FalloutNV34.esm')):
        original_plan=source/(game+'_transfer_plan.jsonl')
        audit=json.loads((source/(game+'_independent_merge_validation.json')).read_text('utf-8'))
        report=json.loads((source/(game+'_merge_plan_report.json')).read_text('utf-8'))
        if audit['status']!='PASS' or audit['verified']['edited_fields']!=report['fields_to_transfer']:
            raise ValueError(f'Not verified independently: {game}')
        dest=output/(game+'.utf8.text-fields.jsonl.gz')
        counts=collections.Counter();seen=set()
        with original_plan.open('r',encoding='utf-8') as inp, dest.open('wb') as output_bin:
            with gzip.GzipFile(fileobj=output_bin,mode='wb',filename='',mtime=0,compresslevel=8) as gz:
                for line in inp:
                    source_row=json.loads(line)
                    key=(source_row['record_type'],source_row['formid'],source_row['field'],source_row['index'])
                    if key in seen:raise ValueError(f'Duplicate translation {key}')
                    seen.add(key)
                    before=bytes.fromhex(source_row['before_bytes']);after=bytes.fromhex(source_row['after_bytes'])
                    if before==after:raise ValueError('Unchanged field in delta')
                    if not after.endswith(b'\x00') or b'\x00' in after[:-1]:
                        raise ValueError('Not a NUL terminated UTF-8 text field')
                    clean=after[:-1].decode('utf-8')
                    if '\ufffd' in clean or not any('\uac00'<=c<='\ud7a3' for c in clean):
                        raise ValueError('Invalid Korean UTF-8 field')
                    record={'id':source_row['formid'],'type':source_row['record_type'],
                            'field':source_row['field'],'index':source_row['index'],
                            'edid':source_row['edid'],'before_sha256':hashlib.sha256(before).hexdigest(),
                            'korean':clean}
                    gz.write((json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8'))
                    counts[source_row['record_type']+':'+source_row['field']]+=1
        if len(seen)!=audit['verified']['edited_fields']:
            raise ValueError(f'Translation field count mismatch {game}')
        manifest['games'][game]={'esm_filename':name,
              'base_esm_sha256':audit['data_source_sha256'],
              'verified_local_output_sha256':audit['merged_sha256'],
              'text_field_file':dest.relative_to(ROOT).as_posix(),
              'text_field_file_sha256':digest(dest),'text_field_count':len(seen),
              'record_field_counts':dict(sorted(counts.items())),
              'non_text_records':'not included; source full terrain ESM is required on user PC'}
        print('EXPORTED',game,len(seen),'compressed bytes',dest.stat().st_size,'sha256',digest(dest),flush=True)
    target=output/'manifest.json'
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('MANIFEST',target,flush=True)
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=pathlib.Path,default=DEFAULT_INPUT)
    p.add_argument('--output',type=pathlib.Path,default=OUT)
    args=p.parse_args();build(args.source,args.output)
