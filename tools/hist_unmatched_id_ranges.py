from pathlib import Path
from collections import Counter,defaultdict
import gzip,json
folder=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\data\fo3')
count=Counter();types=defaultdict(Counter);samples=defaultdict(list)
for line in gzip.open(folder/'unmatched_field_entries.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 fid=int(r['target_formid'],16)
 band=f'{fid>>20:03X}'  # 0x010 to 0x01f etc
 count[band]+=1;types[band][r['record_type']]+=1
 if len(samples[band])<5:samples[band].append((r['target_formid'],r['record_type'],r['english'][:90]))
for band,n in count.most_common():
 print(band,n,types[band].most_common(6),samples[band][:2])
