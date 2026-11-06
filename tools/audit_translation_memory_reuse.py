"""Assess untranslated string candidates against existing FO3 SST translation memory. Read only."""
from collections import defaultdict,Counter
from pathlib import Path
import json,gzip,importlib.util
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
out=root/'data'/'fo3'
mod=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\tools\read_xtranslator_sst.py')
spec=importlib.util.spec_from_file_location('sst_reader',mod)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
names=['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta']
by_exact=defaultdict(set);by_type=defaultdict(set);by_english=defaultdict(set)
for name in names:
 s=m.parse_sst(folder/(name+'_en_ko.sst'))
 masters=[x.casefold() for x in s['master_files']]
 for r in s['records']:
  i=int(r['form_id'],16)>>24
  if i>=len(masters):continue
  if masters[i] not in ('fallout3.esm','anchorage.esm','thepitt.esm','brokensteel.esm','pointlookout.esm','zeta.esm'):continue
  e,k=r['source'],r['korean']
  if not e.strip() or not k.strip() or e==k:continue
  by_exact[(r['record_name'],r['field_name'],e)].add(k)
  by_type[(r['record_name'],e)].add(k)
  by_english[e].add(k)
print('DICTIONARY ENGLISH KEYS',len(by_english),'EXACT',len(by_exact),flush=True)
n=0;count=Counter();by_type_count=defaultdict(Counter);samples=defaultdict(list);unique_all=set()
manual=[];strong=[];variants=[]
for line in gzip.open(out/'unmatched_field_entries.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 n+=1
 t,f,e=r['record_type'],r['field'],r['english']
 unique_all.add((r['target_formid'],t,f,e))
 if int(r['target_formid'],16)>>24==0:
  key='fo4_base_plugin'
 elif (t,f,e) in by_exact and len(by_exact[(t,f,e)])==1:
  key='unique_ko_same_type_field'
 elif (t,e) in by_type and len(by_type[(t,e)])==1:
  key='unique_ko_same_type_any_field'
 elif e in by_english and len(by_english[e])==1:
  key='unique_ko_any_type_field'
 elif e in by_english:
  key='conflicting_ko_for_same_english'
 else:
  key='no_fo3_sst_english_match'
 count[key]+=1;by_type_count[t][key]+=1
 if len(samples[key])<10:samples[key].append(r)
 if key=='unique_ko_same_type_field':
  r['korean']=next(iter(by_exact[(t,f,e)]));r['match_class']=key;strong.append(r)
 elif key.startswith('unique_ko_'):
  r['korean']=next(iter(by_type[(t,e)] if key=='unique_ko_same_type_any_field' else by_english[e]));r['match_class']=key;variants.append(r)
 else:manual.append(r)
def write(name,rows):
 with gzip.open(out/name,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
write('potential_sst_reuse_strong.jsonl.gz',strong)
write('potential_sst_reuse_context_review.jsonl.gz',variants)
summary={'unmatched_occurrences':n,'unique_target_field_text_combinations':len(unique_all),'counts':dict(count),'by_type':{t:dict(c) for t,c in by_type_count.items()},'examples':dict(samples),'warning':'These are matches by English text, NOT record/field provenance. All require context check. Do NOT auto-apply across unrelated items or generic lines.'}
(out/'sst_reuse_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('UNMATCHED',n,'UNIQUE',len(unique_all),'COUNTS',dict(count))
for t,c in sorted(by_type_count.items(),key=lambda i:-sum(i[1].values()))[:20]:
 print('TYPE',t,sum(c.values()),dict(c))
