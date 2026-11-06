from pathlib import Path
from collections import Counter,defaultdict
import re,gzip,json
folder=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\data\fnv')
broad=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[a-zA-Z]|&[A-Za-z_][A-Za-z0-9_]*;|<[^<>\r\n]{1,80}>|\{\w+\}')
safe=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}')
reason=Counter();broad_examples=defaultdict(list)
for line in gzip.open(folder/'provenance_qa_review.jsonl.gz','rt',encoding='utf-8'):
 row=json.loads(line)
 a,b=Counter(safe.findall(row['english'])),Counter(safe.findall(row['korean']))
 if a!=b:
  cls='real_placeholder_mismatch'
  if len(broad_examples[cls])<8:broad_examples[cls].append({'eng':row['english'][:160],'ko':row['korean'][:160],'old':broad.findall(row['english'])[:10],'new':broad.findall(row['korean'])[:10],'safes':list(a),'safek':list(b)})
 else:
  cls='false_positive_markup'
  if len(broad_examples[cls])<5:broad_examples[cls].append({'eng':row['english'][:160],'ko':row['korean'][:160],'old':broad.findall(row['english'])[:10],'new':broad.findall(row['korean'])[:10]})
 reason[cls]+=1
print('COUNTS',reason)
print('SAMPLES',json.dumps(dict(broad_examples),ensure_ascii=True)[:2900])
