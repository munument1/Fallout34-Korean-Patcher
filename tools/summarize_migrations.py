from collections import Counter,defaultdict
from pathlib import Path
import json,gzip
f=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\data\fo3\possible_field_migrations.jsonl.gz')
count=Counter();unique=set();sample=defaultdict(list)
for line in gzip.open(f,'rt',encoding='utf-8'):
 obj=json.loads(line);r=obj['row']
 for field in obj['matching_fields']:
  count[(r['record_type'],r['field'],field)]+=1
  if len(sample[(r['record_type'],r['field'],field)])<3:sample[(r['record_type'],r['field'],field)].append((r['source_key'],r['english'][:90],r['korean'][:90]))
 unique.add((r['target_formid'],r['record_type'],r['field'],r['english']))
print('MIGRATION_ROWS',len(unique),'COUNT',sum(count.values()))
for k,v in count.most_common():print('MIG',k,v,'SAMPLE',str(sample[k])[:500])
