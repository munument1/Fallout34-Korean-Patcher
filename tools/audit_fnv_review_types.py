from pathlib import Path
from collections import Counter,defaultdict
import gzip,json
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\data\fnv')
c=defaultdict(Counter);fields=defaultdict(Counter);samples=defaultdict(list);types=Counter()
for line in gzip.open(root/'review_needed.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 key=r['validation_status']
 c[key][r['record_type']]+=1
 fields[key][(r['record_type'],r['field'])]+=1
 if len(samples[key])<8:samples[key].append((r['target_formid'],r['record_type'],r['field'],r['english'][:90],r['korean'][:90],r['mapping_method']))
for reason in c:
 print('REASON',reason,'TYPE',c[reason].most_common(20))
 print('FIELD',fields[reason].most_common(17))
 print('EXAMPLES',json.dumps(samples[reason],ensure_ascii=True)[:1200])
