"""Read-only verifier for both converted ESM SHA pins, indexed translation plans and shared MCM."""
from collections import Counter
from pathlib import Path
import gzip,hashlib,json,re,sys
root=Path(__file__).resolve().parents[1]
base=Path(r'C:\Games\Steam\steamapps\common\Fallout 4')
checks=[]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for data in iter(lambda:f.read(8*1024*1024),b''):h.update(data)
 return h.hexdigest()
def strip_ui(obj):
 if isinstance(obj,dict):return {k:strip_ui(v) for k,v in obj.items() if k not in ('text','displayName','pageDisplayName','help','options')}
 if isinstance(obj,list):return [strip_ui(v) for v in obj]
 return obj
for game,plugin in [('fo3','Fallout34.esm'),('fnv','FalloutNV34.esm')]:
 folder=root/'data'/game
 report=json.loads((folder/'indexed_plan_report.json').read_text(encoding='utf-8'))
 game_esm=base/'Data'/plugin
 if not game_esm.is_file() and game=='fnv':game_esm=base/'Fallout34_Work'/'fnv'/'staging'/'Data'/plugin
 if not game_esm.is_file():raise FileNotFoundError('Missing source ESM '+str(game_esm))
 actual_sha=sha(game_esm)
 if actual_sha!=report['esm_sha256']:raise RuntimeError('ESM hash changed for '+game)
 known=set();count=0;origin=Counter();duplicates=0
 with gzip.open(folder/'indexed_patch_plan_candidates.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   row=json.loads(line)
   key=(row['target_formid'],row['record_type'],row['field'],row['target_field_occurrence_index'])
   if key in known:duplicates+=1
   known.add(key)
   origin[row['plan_source']]+=1
   if not row['english'] or not row['korean'] or row['english']==row['korean']:raise RuntimeError('Invalid translation '+game+' '+str(key))
   count+=1
 if duplicates:raise RuntimeError(f'Duplicate planned target fields {game}: {duplicates}')
 if count!=report['indexed_unique_candidate_rows']:raise RuntimeError('Plan row count differs report '+game)
 checks.append({'game':game,'esm_path':str(game_esm),'esm_hash_verified':True,'expected_sha256':actual_sha,'indexed_assignments':count,'unique_target_occurrences':len(known),'plan_sources':dict(origin),'ready_for_ingame_test':False})
ko=root/'work'/'common'/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
original=base/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
if not ko.is_file() or not original.is_file():raise FileNotFoundError('MCM files not present')
translated=json.loads(ko.read_text(encoding='utf-8-sig'))
source=json.loads(original.read_text(encoding='utf-8-sig'))
if strip_ui(source)!=strip_ui(translated):raise RuntimeError('MCM functional data changed')
report={'source_esm_hashes_match':True,'translated_mcm_non_ui_data_unchanged':True,'mcm_korean_path':str(ko),'checks':checks,'count_total':sum(x['indexed_assignments'] for x in checks),'status':'All static checks passed; this does not constitute an installed or runtime-tested ESP.'}
(root/'data'/'bundle_static_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',json.dumps({'source_esm_hashes_match':True,'shared_mcm_verified':True,'total':report['count_total'],'games':{x['game']:x['indexed_assignments'] for x in checks},'esm_paths':{x['game']:x['esm_path'] for x in checks}},ensure_ascii=True),flush=True)
