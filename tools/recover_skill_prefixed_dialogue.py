"""Derive Korean skill-check label plus existing translated line, preserving actual numeric/global tokens."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,re,importlib.util
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
spec=importlib.util.spec_from_file_location('sst',ROOT/'tools'/'read_xtranslator_sst.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
files={'fo3':['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta'],'fnv':['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal']}
LABELS={'Speech':'화술','Science':'과학','Intelligence':'지능','Medicine':'의학',
 'Barter':'흥정','Strength':'힘','Perception':'인지력','Endurance':'지구력',
 'Repair':'수리','Agility':'민첩','Small Guns':'소형 화기','Explosives':'폭발물',
 'Luck':'운','Sneak':'은신','Charisma':'매력','Lockpick':'자물쇠 따기',
 'Energy Weapons':'에너지 무기','Unarmed':'격투','Melee Weapons':'근접 무기',
 'FAILED':'실패','SUCCEEDED':'성공'}
def clean(s):
 return re.sub(r'^\s*(?:\{[^{}]{1,160}\}\s*)+','',s.lstrip('\ufeff')).strip()
BRACKET=re.compile(r'^\[([A-Za-z ]+?)(?:\s+(\d+|<Global=[^>]{1,120}>%))?\]\s*')
for game,parts in files.items():
 sources=defaultdict(set)
 for name in parts:
  s=module.parse_sst(folder/(name+'_en_ko.sst'))
  masters=[x.casefold() for x in s['master_files']]
  for r in s['records']:
   num=int(r['form_id'],16)
   if num>>24>=len(masters):continue
   k=(masters[num>>24]+f':{num&0xffffff:06x}',r['record_name'],r['field_name'],clean(r['source']))
   if r['korean'] and r['korean']!=r['source']:sources[k].add(r['korean'])
 results=Counter();samples=defaultdict(list);strong=[];medium=[];review=[]
 path=ROOT/'data'/game
 for line in gzip.open(path/'normalized_dialogue_review.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line)
  if r['editor_normalize_class']!='skill_prefix_added_to_original_english':continue
  m=BRACKET.match(r['english'])
  if not m or m.group(1) not in LABELS:
   cls='unknown_skill_prefix';translated=None
  else:
   tag=m.group(1)
   literal=(' '+m.group(2)) if m.group(2) else ''
   korean_prefix='['+LABELS[tag]+literal+']'
   suffix=r['english'][m.end():].strip()
   typ,field=r['record_type'],r['field']
   preferred=[(typ,field)]
   if (typ,field)==('INFO','RNAM'):preferred=[('DIAL','FULL'),('INFO','RNAM'),('INFO','NAM1')]
   if (typ,field)==('INFO','NAM1'):preferred=[('INFO','NAM1'),('DIAL','FULL')]
   by_original=set()
   for origin in r['original_source_keys']:
    for t,f in preferred:
     by_original.update(sources.get((origin,t,f,suffix),set()))
   if len(by_original)==1:
    cls='same_original_source_skill_prefix'
    translated=korean_prefix+' '+next(iter(by_original))
   elif len(by_original)>1:
    cls='source_skill_multiple_korean';translated=None
   else:
    possible=r.get('suggested_korean','')
    if possible:
     cls='same_english_skill_prefix_no_source'
     translated=korean_prefix+' '+possible
    else:cls='no_skill_korean_found';translated=None
  results[cls]+=1
  if len(samples[cls])<5:samples[cls].append({'en':r['english'][:150],'ko':translated[:150] if translated else None,'formid':r['target_formid'],'origins':r['original_source_keys'][:3]})
  record=dict(r);record['skill_recovery_class']=cls
  if translated:record['korean']=translated
  (strong if cls=='same_original_source_skill_prefix' else medium if translated else review).append(record)
 def write(name,rows):
  with gzip.open(path/name,'wt',encoding='utf-8',compresslevel=6) as f:
   for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
 write('skill_source_verified_suggestions.jsonl.gz',strong)
 write('skill_text_only_suggestions.jsonl.gz',medium)
 write('skill_unresolved.jsonl.gz',review)
 report={'counts':dict(results),'examples':dict(samples),'status':'uninstalled patch suggestions','warning':'Skill prefix translated while preserving numeric and global expression. Source-ID matches are stronger; text-only remains manual review.'}
 (path/'skill_label_recovery_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('GAME',game,'COUNTS',dict(results),'EXAMPLES',json.dumps({k:v[:2] for k,v in samples.items()},ensure_ascii=True)[:1600],flush=True)
