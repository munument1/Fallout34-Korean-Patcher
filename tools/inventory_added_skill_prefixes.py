from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
for game in ('fo3','fnv'):
 d=root/'data'/game;counts=Counter();bycat=defaultdict(Counter);examples=defaultdict(list)
 for line in gzip.open(d/'normalized_dialogue_review.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line)
  if r['editor_normalize_class']!='skill_prefix_added_to_original_english':continue
  en=r['english'];m=re.match(r'^\s*(\[[^\]]{1,120}\])',en)
  label=m.group(1) if m else 'no bracket'
  # normalize digit/global to inspect name
  tag=re.sub(r'\d+','N',re.sub(r'<Global=[^>]+>','<Global>',label))
  counts[tag]+=1;bycat[r['record_type']+'/'+r['field']][tag]+=1
  if len(examples[tag])<2:examples[tag].append({'en':en[:135],'ko':r.get('suggested_korean','')[:140],'origin':r.get('original_source_keys',[])[:2]})
 print('GAME',game,'LABELS',counts.most_common(50),flush=True)
 print('EXAMPLES',json.dumps({k:v for k,v in list(examples.items())[:15]},ensure_ascii=True)[:3500],flush=True)
