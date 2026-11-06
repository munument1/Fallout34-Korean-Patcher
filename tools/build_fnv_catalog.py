"""Safely import Fallout NV SST entries and match converted FalloutNV34 FormIDs. Never modifies inputs."""
from pathlib import Path
from collections import defaultdict,Counter
import csv, gzip, json, importlib.util
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
out=root/'data'/'fnv';out.mkdir(parents=True,exist_ok=True)
work=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv')
source=work/'work'/'reports'/'formid_map.tsv'
sst_folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
py=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\tools\read_xtranslator_sst.py')
spec=importlib.util.spec_from_file_location('sst',py);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
names=['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal','caravanpack','classicpack','mercenarypack','tribalpack']
allowed={x+'.esm' for x in names}
rows=[];by_source=defaultdict(list);source_count=Counter()
for name in names:
 p=sst_folder/(name+'_en_ko.sst')
 if not p.is_file():print('MISSING',p);continue
 parsed=mod.parse_sst(p)
 masters=[x.casefold() for x in parsed['master_files']]
 eligible=0
 for orig in parsed['records']:
  fid=int(orig['form_id'],16)
  idx=fid>>24
  if idx>=len(masters):continue
  plugin=masters[idx]
  if plugin not in allowed:continue
  key=f'{plugin}:{fid&0xffffff:06x}'
  row={'source_key':key,'source_plugin':plugin,'source_formid':orig['form_id'],'record_type':orig['record_name'],'field':orig['field_name'],'sub_index':orig['index'],'sub_index_max':orig['index_max'],'english':orig['source'],'korean':orig['korean'],'sst_file':p.name,'sst_sha256':parsed['sha256'],'status_flags':orig['status_flags_raw']}
  if not row['korean'] or row['korean']==row['english']:continue
  pos=len(rows);rows.append(row);by_source[(key,orig['record_name'])].append(pos);eligible+=1
 source_count[name]=eligible
 print('SST',p.name,'translated eligible',eligible,flush=True)
mstats=Counter();mapped_keys=set();mapped_rows=0;matches_by_method=Counter();by_key_recs=Counter();fused=Counter()
map_input=source if source.is_file() else out/'converter_formid_map.tsv.gz'
if not map_input.is_file():raise FileNotFoundError('Need converter FormID map or checked-in snapshot')
map_open=gzip.open if map_input.suffix=='.gz' else open
with map_open(map_input,'rt',encoding='utf-8',newline='') as f:
 for row in csv.DictReader(f,delimiter='\t'):
  mstats['map_total']+=1
  pair=(row['source'].casefold(),row['type'])
  if pair not in by_source:continue
  by_key_recs[pair]+=1
  for i in by_source[pair]:
   rec=rows[i]
   if rec.get('target_formid') and rec['target_formid']!=row['formid']:
    fused[rec['source_key']]+=1;continue
   rec['target_formid']=row['formid']
   rec['mapping_method']='explicit_formid_map'
   mapped_rows+=1
  mapped_keys.add(pair)
# FNV main ESM often has original low 24-bit record ids unchanged. Probe below only if direct map is absent.
for i,rec in enumerate(rows):
 if 'target_formid' in rec:continue
 if rec['source_plugin']=='falloutnv.esm':
  low=int(rec['source_key'].split(':')[1],16)
  rec['target_formid']=f'{0x01000000+low:08X}'
  rec['mapping_method']='base_direct_id_probe_pending_esm_text'
  matches_by_method['base_id_fallback']+=1
stats={'source_sst_records':len(rows),'source_sst_file_counts':dict(source_count),'total_formid_map_rows':mstats['map_total'],'explicit_mapped_sst_rows':mapped_rows,'explicit_mapped_source_pairs':len(mapped_keys),'base_direct_id_probe':matches_by_method['base_id_fallback'],'map_duplicate_source_type_pairs':sum(n>1 for n in by_key_recs.values()),'conflicting_map_ids':dict(fused),'remaining_no_id':sum('target_formid' not in r for r in rows)}
def dump(name,recs):
 with gzip.open(out/name,'wt',encoding='utf-8',compresslevel=6) as f:
  for row in recs:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
dump('formid_candidates.jsonl.gz',(r for r in rows if 'target_formid' in r))
dump('sst_unmapped.jsonl.gz',(r for r in rows if 'target_formid' not in r))
(out/'catalog_report.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('REPORT',json.dumps(stats,ensure_ascii=True),flush=True)
