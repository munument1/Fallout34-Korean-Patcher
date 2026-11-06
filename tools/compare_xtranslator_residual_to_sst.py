"""Cross-check xTranslator-recognized yet unassigned ESM text against BOTH FO3 and FNV SST translation sources.
This is a candidate classifier, never a blind translation applier.
"""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,csv,importlib.util,re
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
spec=importlib.util.spec_from_file_location('sst',ROOT/'tools'/'read_xtranslator_sst.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FOLDER=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
SETS={'fo3':['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta'],
      'fnv':['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal','caravanpack','classicpack','mercenarypack','tribalpack']}
trans=defaultdict(set);noncontext=defaultdict(set);normalized=defaultdict(set);sources=Counter()
def no_edit_braces(t):
 return re.sub(r'^\s*(?:\{[^{}]{1,160}\}\s*)+','',t).strip()
for game,names in SETS.items():
 for name in names:
  s=m.parse_sst(FOLDER/(name+'_en_ko.sst'))
  translated=0
  for row in s['records']:
   en,ko=row['source'],row['korean']
   if not en or not ko or en==ko:continue
   trans[(game,row['record_name'],row['field_name'],en)].add(ko)
   noncontext[(game,en)].add(ko)
   cleaned=no_edit_braces(en)
   if cleaned!=en:normalized[(game,row['record_name'],row['field_name'],cleaned)].add(ko)
   translated+=1
  sources[game]+=translated
print('SST ROWS',dict(sources),flush=True)
for game in ('fo3','fnv'):
 d=ROOT/'data'/game
 stats=Counter();per_field=defaultdict(Counter);samples=defaultdict(list);distinct=defaultdict(set)
 review=[]
 other='fnv' if game=='fo3' else 'fo3'
 with gzip.open(d/'xtranslator_residual_candidates.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   r=json.loads(line)
   if r['status']!='missing_translation_match':continue
   en=r['english'];t=r['record_type'];fld=r['field']
   method=''
   candidates=trans[(game,t,fld,en)]
   if len(candidates)==1:method='same_game_exact_type_field_unique'
   elif len(candidates)>1:method='same_game_exact_type_field_conflict'
   else:
    candidates=normalized[(game,t,fld,en)]
    if len(candidates)==1:method='same_game_edit_cue_stripped_unique'
    elif len(candidates)>1:method='same_game_edit_cue_stripped_conflict'
    else:
     candidates=trans[(other,t,fld,en)]
     if len(candidates)==1:method='other_game_exact_type_field_unique'
     elif len(candidates)>1:method='other_game_exact_type_field_conflict'
     else:
      candidates=noncontext[(game,en)]
      if len(candidates)==1:method='same_game_different_field_unique'
      elif len(candidates)>1:method='same_game_different_field_conflict'
      else:
       candidates=noncontext[(other,en)]
       if len(candidates)==1:method='other_game_different_field_unique'
       elif len(candidates)>1:method='other_game_different_field_conflict'
       else:method='no_matching_english_in_either_sst'
   stats[method]+=1;per_field[t+'/'+fld][method]+=1;distinct[method].add((t,fld,en))
   if len(samples[method])<8:samples[method].append({'formid':r['formid'],'record_type':t,'field':fld,'english':en[:140],'suggested_korean':list(candidates)[:2]})
   r['sst_match_status']=method
   if len(candidates)==1:r['candidate_korean']=next(iter(candidates))
   review.append(r)
 csv_name=d/'xtranslator_sst_gap_review.csv'
 with csv_name.open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.writer(f)
  writer.writerow(['priority','record_type','field','english_json','count_occurrences','match_class','korean_candidate_json','example_formids'])
  grouped={}
  for r in review:
   key=(r['priority'],r['record_type'],r['field'],r['english'],r['sst_match_status'],r.get('candidate_korean',''))
   if key not in grouped:grouped[key]=[0,[]]
   grouped[key][0]+=1
   if len(grouped[key][1])<3:grouped[key][1].append(r['formid'])
  for (p,t,fld,en,method,ko),(count,ids) in sorted(grouped.items(),key=lambda x:(x[0][0],-x[1][0],x[0][1],x[0][2])):
   writer.writerow([p,t,fld,json.dumps(en,ensure_ascii=False),count,method,json.dumps(ko,ensure_ascii=False),';'.join(ids)])
 summary={'game':game,'sst_records_with_translation_per_game':dict(sources),'unassigned_xtranslator_text_occurrences':sum(stats.values()),'distinct_type_field_english_matches':sum(len(v) for v in distinct.values()),'classification':dict(stats),'classification_distinct':{k:len(v) for k,v in distinct.items()},'by_field':{k:dict(v) for k,v in per_field.items()},'examples':dict(samples),'warning':'This cross-check uses English identity (including optional leading editor stage-direction cues), NOT sufficient to assign a translation to a record. Do not auto-apply without provenance/field context.'}
 (d/'xtranslator_sst_compare_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('GAME',game,'COUNTS',dict(stats),'UNIQUE',summary['classification_distinct'],flush=True)
 print('TOP MISSING FIELDS',[(k,v.get('no_matching_english_in_either_sst',0)) for k,v in sorted(per_field.items(),key=lambda x:-x[1].get('no_matching_english_in_either_sst',0))[:16]],flush=True)
