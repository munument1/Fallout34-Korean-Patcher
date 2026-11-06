"""Recover FalloutNV34 dynamically generated UI text by converter-provided source provenance, not by blind English matching."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,csv,importlib.util,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
out=root/'data'/'fnv'
work=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv')
keys=work/'work'/'reports'/'formid_keys.tsv'
sst_reader=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\tools\read_xtranslator_sst.py')
spec=importlib.util.spec_from_file_location('sst',sst_reader)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
files=['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal','caravanpack','classicpack','mercenarypack','tribalpack']
by_origin=defaultdict(lambda:defaultdict(set));by_global=defaultdict(set);by_type=defaultdict(lambda:defaultdict(set))
for name in files:
 p=folder/(name+'_en_ko.sst')
 if not p.exists():continue
 parsed=mod.parse_sst(p);masters=[x.casefold() for x in parsed['master_files']]
 for r in parsed['records']:
  fid=int(r['form_id'],16);i=fid>>24
  if i>=len(masters):continue
  plugin=masters[i]
  if not plugin.endswith('.esm'):continue
  if not r['korean'] or r['korean']==r['source']:continue
  source=f'{plugin}:{fid&0xffffff:06x}'
  by_origin[source][r['source']].add(r['korean'])
  by_global[r['source']].add(r['korean'])
  by_type[r['record_name']][r['source']].add(r['korean'])
print('SST ORIGINS',len(by_origin),'GLOBAL',len(by_global),flush=True)
unlinked=defaultdict(list);total=0
with gzip.open(out/'unlinked_field_entries.jsonl.gz','rt',encoding='utf-8') as f:
 for line in f:
  r=json.loads(line)
  total+=1;unlinked[r['target_formid']].append(r)
print('NEED TARGET IDS',len(unlinked),'OCCURRENCES',total,flush=True)
source_ids=defaultdict(list);keys_seen=Counter();samplekeys=[];generated_ids=0
# A generated FormID can have several original records mentioned. All source IDs are matched as tokens.
pattern=re.compile(r'(?i)^([a-z0-9._ \-]+\.esm):([a-f0-9]{6})$')
key_input=keys if keys.is_file() else out/'converter_origin_keys_selected.tsv.gz'
if not key_input.is_file():raise FileNotFoundError('Need generated key index')
key_open=gzip.open if key_input.suffix=='.gz' else open
with key_open(key_input,'rt',encoding='utf-8') as f:
 for line in f:
  try:target,typ,probe,key=line.rstrip('\r\n').split('\t',3)
  except ValueError:continue
  if target not in unlinked:continue
  keys_seen[(typ,key.split('|')[1] if '|' in key else '<no-tag>')]+=1
  generated_ids+=1
  origins=[]
  for seg in key.split('|'):
   match=pattern.fullmatch(seg)
   if match:origins.append(match.group(1).casefold()+':'+match.group(2).casefold())
  source_ids[target].extend(origins)
  if len(samplekeys)<10:samplekeys.append({'id':target,'key':key[:180],'origins':origins})
print('MATCHED KEY TARGET IDS',len(source_ids),'KEY ROWS',generated_ids,'TOP',keys_seen.most_common(12),flush=True)
status=Counter();by_pair=defaultdict(Counter);examples=defaultdict(list);matched=[];risk=[];origin_count=Counter()
for fid,rows in unlinked.items():
 origins=list(dict.fromkeys(source_ids.get(fid,[])))
 for r in rows:
  english=r['english'];korean=set()
  observed=[]
  for origin in origins:
   ks=by_origin.get(origin,{}).get(english,set())
   if ks:
    korean.update(ks);observed.append(origin)
  if not origins:cls='key_no_original_id'
  elif not observed:cls='key_origin_no_matching_SST_english'
  elif len(korean)>1:cls='key_origin_multiple_korean'
  elif len(observed)==1:cls='one_matching_origin_unique_korean'
  else:cls='multiple_matching_origins_same_korean'
  status[cls]+=1;by_pair[(r['record_type'],r['field'])][cls]+=1
  origin_count[len(origins)]+=1
  if len(examples[cls])<7:examples[cls].append({'target':fid,'type':r['record_type'],'field':r['field'],'english':english[:100],'origins':origins[:6],'matching_origins':observed[:5],'korean':list(korean)[:2]})
  item=dict(r);item.update({'source_key_origins':origins[:30],'matched_source_origins':observed[:30],'match_class':cls})
  if len(korean)==1:item['korean']=next(iter(korean))
  (matched if cls in ('one_matching_origin_unique_korean','multiple_matching_origins_same_korean') else risk).append(item)
def write(name,values):
 with gzip.open(out/name,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in values:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
write('provenance_text_candidates.jsonl.gz',matched)
write('provenance_text_review.jsonl.gz',risk)
report={'total_unlinked_occurrences':total,'target_ids_from_keys':len(source_ids),'key_rows':generated_ids,'class_counts':dict(status),'per_type_field':{f'{a}/{b}':dict(v) for (a,b),v in sorted(by_pair.items(),key=lambda kv:-sum(kv[1].values()))},'generated_key_categories':[(list(k),v) for k,v in keys_seen.most_common(30)],'source_origins_count_histogram':dict(origin_count),'sample_keys':samplekeys,'examples':dict(examples),'warning':'Source provenance from converter key and exact SST English; still requires ambiguity and runtime response-index validation. Do not auto-install.'}
(out/'generated_provenance_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('REPORT',json.dumps({k:v for k,v in report.items() if k not in ('per_type_field','generated_key_categories','source_origins_count_histogram','sample_keys','examples','warning')},ensure_ascii=True),flush=True)
print('INFO_RNAM',report['per_type_field'].get('INFO/RNAM'),flush=True)
print('INFO_NAM1',report['per_type_field'].get('INFO/NAM1'),flush=True)
print('TERM_UNAM',report['per_type_field'].get('TERM/UNAM'),flush=True)
print('EXAMPLES',json.dumps({k:v[:2] for k,v in examples.items()},ensure_ascii=True)[:2400])
