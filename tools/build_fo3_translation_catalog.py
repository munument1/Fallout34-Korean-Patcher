from __future__ import annotations
import csv, hashlib, importlib.util, json, gzip, re
from collections import Counter, defaultdict
from pathlib import Path
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
src=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3')
sst_reader=Path(r'D:\Codex_Trans\BGS_Translation_Archive\tools\read_xtranslator_sst.py')
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
spec=importlib.util.spec_from_file_location('sst_reader',sst_reader)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
names=['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta']
cache={}
summary={'sst_files':[],'sst_records':0,'eligible_fo3_records':0,'matching_mapped_records':0}
rows=[]
sources_by_pair=defaultdict(list)
for name in names:
    path=folder/(name+'_en_ko.sst')
    parsed=module.parse_sst(path)
    masters=[x.casefold() for x in parsed['master_files']]
    scanned=0
    eligible=0
    for row in parsed['records']:
        scanned+=1
        fid=int(row['form_id'],16)
        mid=fid>>24
        if mid>=len(masters):continue
        plugin=masters[mid]
        if plugin not in ('fallout3.esm','anchorage.esm','thepitt.esm','brokensteel.esm','pointlookout.esm','zeta.esm'):continue
        eligible+=1
        source_key=plugin+':'+f'{fid&0xffffff:06x}'
        item={'source_key':source_key,'source_plugin':plugin,'source_formid':row['form_id'],'record_type':row['record_name'],'field':row['field_name'],'sub_index':row['index'],'sub_index_max':row['index_max'],'english':row['source'],'korean':row['korean'],'sst_file':path.name,'sst_hash':parsed['sha256'],'status_flags':row['status_flags_raw']}
        rows.append(item)
        sources_by_pair[(source_key,row['record_name'])].append(len(rows)-1)
    summary['sst_files'].append({'filename':path.name,'count':scanned,'fo3_eligible':eligible,'sha256':parsed['sha256'],'masters':parsed['master_files']})
    summary['sst_records']+=scanned
    summary['eligible_fo3_records']+=eligible
print('SST parsed',len(rows),'eligible FO3 records',len(sources_by_pair),flush=True)
map_file=src/'work'/'reports'/'formid_map.tsv'
map_count=0
matched_sources=set()
map_types=Counter()
with map_file.open('r',encoding='utf-8',newline='') as f:
    for record in csv.DictReader(f,delimiter='\t'):
        map_count+=1
        key=record['source'].casefold()
        pair=(key,record['type'])
        if pair in sources_by_pair:
            for idx in sources_by_pair[pair]:
                rows[idx]['target_formid']=record['formid']
            matched_sources.add(pair)
            map_types[record['type']]+=1
print('Map rows',map_count,'matched pairs',len(matched_sources),flush=True)
out=root/'data'/'fo3'
out.mkdir(parents=True,exist_ok=True)
matched=out/'translation_candidates.jsonl.gz'
missing=out/'unmatched_sst.jsonl.gz'
seen=set()
with gzip.open(matched,'wt',encoding='utf-8',compresslevel=6) as yes, gzip.open(missing,'wt',encoding='utf-8',compresslevel=6) as no:
    for x in rows:
        # preserve duplicates, and avoid assuming all translated strings will have same target ESM fields
        fh=yes if 'target_formid' in x else no
        fh.write(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n')
summary['mapped_candidate_rows']=sum('target_formid' in x for x in rows)
summary['unmapped_candidate_rows']=sum('target_formid' not in x for x in rows)
summary['mapped_target_record_pairs']=len(matched_sources)
summary['total_formid_map_rows']=map_count
summary['mapped_record_types']=dict(map_types.most_common())
summary['important_caution']='Mappings are candidate identifiers, not validated translated ESM output. Verify record field/source English, compression, and variants before patch generation.'
with (root/'data'/'fo3'/'catalog_report.json').open('w',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
print('summary',json.dumps({k:v for k,v in summary.items() if k not in ('sst_files','mapped_record_types')},ensure_ascii=True),flush=True)
print('Top match types',map_types.most_common(10),flush=True)
print('OUTPUT',matched,'bytes',matched.stat().st_size,flush=True)
print('UNMATCHED',missing,'bytes',missing.stat().st_size,flush=True)
