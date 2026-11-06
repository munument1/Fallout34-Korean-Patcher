"""Check if unlinked converted English can be recovered via ORIGINAL ESM provenance + existing SST translation, without auto-applying."""
from pathlib import Path
from collections import Counter,defaultdict
import importlib.util,gzip,json,hashlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
data=root/'data'/'fo3'
reader=Path(r'D:\Codex_Trans\BGS_Translation_Archive\tools\read_xtranslator_sst.py')
spec=importlib.util.spec_from_file_location('sst_reader',reader)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
names=['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta']
translation=defaultdict(set); by_text=defaultdict(set)
for name in names:
 s=mod.parse_sst(folder/(name+'_en_ko.sst'))
 masters=[x.casefold() for x in s['master_files']]
 for r in s['records']:
  fid=int(r['form_id'],16);idx=fid>>24
  if idx>=len(masters):continue
  plugin=masters[idx]
  if plugin not in ('fallout3.esm','anchorage.esm','thepitt.esm','brokensteel.esm','pointlookout.esm','zeta.esm'):continue
  k=r['korean']
  if not k or k==r['source']:continue
  key=(plugin,f'{fid&0xffffff:06x}',r['record_name'],r['field_name'],r['source'])
  translation[key].add(k)
  by_text[r['source']].add(k)
print('SST source keys',len(translation),'English',len(by_text),flush=True)
counts=Counter();tt=defaultdict(Counter); samples=defaultdict(list);provenance=Counter();strong=[];review=[]
for line in gzip.open(data/'generated_source_match_candidates.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 # This list intentionally excludes candidates missing from original entirely.
 srcs=r['source_candidates'];status=r['status'];orig_n=r['source_candidates_count']
 provenance[(r['record_type'],status)]+=1
 if r['record_type'] in ('INFO','TERM') and status in ('same_type_other_field_in_original','different_type_in_original'):
  for orig in srcs[:3]:
   provenance[('source_type',r['record_type'],orig['record_type'],orig['field'])]+=1
 ko=defaultdict(set)
 for orig in srcs:
  key=(orig['plugin'],orig['local_id'],orig['record_type'],orig['field'],r['english'])
  ko[key]=translation.get(key,set())
 distinct=set().union(*ko.values()) if ko else set()
 if status=='same_type_field_in_original' and orig_n==1 and len(distinct)==1:
  match_class='single_original_record_and_translated'
 elif status=='same_type_field_in_original' and distinct and len(distinct)==1:
  match_class='multiple_original_records_same_korean'
 elif len(distinct)==1:
  match_class='some_original_field_translation_same_korean'
 elif len(distinct)>1:
  match_class='different_translations_for_source'
 elif r['english'] in by_text and len(by_text[r['english']])==1:
  match_class='english_only_ko_unique'
 elif r['english'] in by_text:
  match_class='english_only_ko_conflict'
 else:
  match_class='no_fo3_sst_translation_found'
 counts[match_class]+=1;tt[r['record_type']][match_class]+=1
 if len(samples[match_class])<7:
  samples[match_class].append({'target':r['target_formid'],'type':r['record_type'],'field':r['field'],'english':r['english'][:95],'source_count':orig_n,'original_example':srcs[:2],'korean':list(distinct)[:2]})
 r['match_class']=match_class
 if len(distinct)==1:r['possible_korean']=next(iter(distinct))
 elif r['english'] in by_text and len(by_text[r['english']])==1:r['possible_korean']=next(iter(by_text[r['english']]))
 (strong if match_class=='single_original_record_and_translated' else review).append(r)
report={'source_indexed_candidates':sum(counts.values()),'classes':dict(counts),'by_target_type':{k:dict(v) for k,v in tt.items()},'original_source_type_field_samples':[(list(k),v) for k,v in provenance.most_common(35)],'samples':dict(samples),'warning':'Even unique original+SST match is a PATCH CANDIDATE, not proof of running in-game context. Generated IDs must use correct FO4 record and response index.'}
(data/'original_translation_recovery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with gzip.open(data/'original_translation_strong_candidates.jsonl.gz','wt',encoding='utf-8') as f:
 for r in strong:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
with gzip.open(data/'original_translation_review_candidates.jsonl.gz','wt',encoding='utf-8') as f:
 for r in review:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
print('TOTAL',report['source_indexed_candidates'],'CLASSES',dict(counts),flush=True)
print('INFO',dict(tt.get('INFO',{})),'TERM',dict(tt.get('TERM',{})),flush=True)
print('PROVENANCE',provenance.most_common(25),flush=True)
print('SAMPLES',json.dumps({k:v[:2] for k,v in samples.items()},ensure_ascii=True)[:2900])
