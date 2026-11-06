from pathlib import Path
from collections import Counter
path=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv\work\reports\formid_keys.tsv')
counts=Counter();example={};special=0
with path.open('r',encoding='utf-8') as f:
 for line in f:
  part=line.rstrip('\n').split('\t',3)
  if len(part)!=4:continue
  fid,typ,probe,key=part
  if typ not in ('INFO','DIAL','TERM'):continue
  tag=key.split('|',3)[1] if '|' in key else '<unknown>'
  counts[(typ,tag)]+=1
  if (typ,tag) not in example:example[(typ,tag)]=(fid,key[:220])
print('TOP',counts.most_common(35))
for k,v in counts.most_common(15):print('SAMPLE',k,example[k])
