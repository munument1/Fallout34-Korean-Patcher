from pathlib import Path
from collections import defaultdict, Counter
import gzip,json,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
for game in ('fo3','fnv'):
 dir=root/'data'/game
 count=defaultdict(Counter);uniqs=defaultdict(lambda:defaultdict(set));samples=defaultdict(list)
 for line in gzip.open(dir/'visible_manual_review.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line);key=r['record_type']+'/'+r['field'];stat=r['translation_status']
  count[key][stat]+=1
  uniqs[key][stat].add(r['english'])
  if stat=='no_translation_in_current_sst' and len(samples[key])<3:samples[key].append(r['english'][:140])
 for line in gzip.open(dir/'visible_reuse_candidates.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line);key=r['record_type']+'/'+r['field'];stat=r['translation_status']
  count[key][stat]+=1;uniqs[key][stat].add(r['english'])
 print('---',game,'---')
 for key,cts in sorted(count.items(),key=lambda p:-sum(p[1].values()))[:25]:
  print(key,'TOTAL',sum(cts.values()),'NO_SST',cts['no_translation_in_current_sst'],'UNIQUE_NO_SST',len(uniqs[key]['no_translation_in_current_sst']),'REUSE',sum(v for k,v in cts.items() if k.endswith('unique_ko')),'UNIQUE_REUSE',len(uniqs[key]['preferred_original_field_unique_ko']),'EXAMPLES',samples[key][:2])
