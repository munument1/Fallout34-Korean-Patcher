from pathlib import Path
from collections import defaultdict,Counter
import importlib.util,gzip,json,re
r=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
spec=importlib.util.spec_from_file_location('sst',r/'tools'/'read_xtranslator_sst.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
by_en=defaultdict(set);by_type=defaultdict(set)
for name in ('falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal'):
 s=m.parse_sst(folder/(name+'_en_ko.sst'))
 for row in s['records']:
  if row['korean'] and row['korean']!=row['source']:
   by_en[row['source']].add(row['korean'])
   by_type[(row['record_name'],row['field_name'],row['source'])].add(row['korean'])
rows=[];cnt=Counter();examples=defaultdict(list)
for line in gzip.open(r/'data'/'fnv'/'visible_manual_review.jsonl.gz','rt',encoding='utf-8'):
 row=json.loads(line)
 if row['record_type']!='PERK' or row['field']!='FULL' or row['translation_status']!='no_translation_in_current_sst':continue
 en=row['english'];base=re.sub(r' \((\d+)\)$','',en)
 if base!=en:
  if len(by_type[('PERK','FULL',base)])==1:status='perk_rank_stripped_exact_type'
  elif len(by_en[base])==1:status='perk_rank_stripped_any_type'
  elif by_en[base]:status='perk_rank_conflicting'
  else:status='perk_rank_no_sst_match'
 else:status='no_rank_suffix'
 cnt[status]+=1
 if len(examples[status])<8:examples[status].append((en,base,list(by_type[('PERK','FULL',base)])[:3],row['target_formid']))
print('PERK RESULT',cnt)
print('SAMPLES',json.dumps(examples,ensure_ascii=True)[:3500])
