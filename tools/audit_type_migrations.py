from collections import defaultdict, Counter
from pathlib import Path
import gzip, json, struct, zlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
data=root/'data'/'fo3'
to_check=defaultdict(list)
for name in ('review_needed.jsonl.gz','direct_formid_review.jsonl.gz','dlc_direct_review.jsonl.gz'):
 for line in gzip.open(data/name,'rt',encoding='utf-8'):
  r=json.loads(line)
  if 'target_formid' in r:
   to_check[int(r['target_formid'],16)].append(r)
def fld(blob):
 i=0;ex=0
 while i+6<=len(blob):
  t,n=struct.unpack_from('<4sH',blob,i);i+=6
  if t==b'XXXX':
   if n!=4 or i+4>len(blob):break
   ex=struct.unpack_from('<I',blob,i)[0];i+=4;continue
  n=ex or n;ex=0
  if i+n>len(blob):break
  yield t.decode('ascii','replace'),blob[i:i+n];i+=n
def deco(b):
 if not b or len(b)>131072 or b'\0' in b[:-1]:return None
 b=b.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=b.decode(codec)
   if all(c.isprintable() or c in '\r\n\t' for c in s):return s
  except UnicodeError:pass
 return None
types=Counter();verified=Counter();exs=defaultdict(list)
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
with esm.open('rb') as f:
 total=esm.stat().st_size;pos=0
 while pos<total:
  f.seek(pos)
  sig,n,flags,fid,_,_=struct.unpack('<4sIIIII',f.read(24))
  if sig==b'GRUP':pos+=24;continue
  if fid in to_check:
   b=f.read(n)
   if flags&0x00040000:
    expected=struct.unpack_from('<I',b)[0]
    b=zlib.decompress(b[4:])
    if len(b)!=expected:raise Exception('zlib mismatch')
   strings=defaultdict(list)
   for t,v in fld(b):
    txt=deco(v)
    if txt is not None:strings[t].append(txt)
   tp=sig.decode('ascii','replace')
   for r in to_check[fid]:
    if r['record_type']!=tp:
     key=(r['record_type'],tp,r['field'])
     types[key]+=1
     exact=(r['field'] in strings and r['english'] in strings[r['field']])
     if exact:verified[key]+=1
     if len(exs[key])<2:exs[key].append({'source':r['source_key'],'english':r['english'][:75],'korean':r['korean'][:75],'target':r['target_formid'],'same_field_exact':exact})
  pos+=24+n
report={'total_type_changed':sum(types.values()),'same_field_exact_count':sum(verified.values()),'by_conversion':[{'original_type':a,'target_type':b,'field':c,'count':v,'same_field_exact':verified[(a,b,c)],'samples':exs[(a,b,c)]} for (a,b,c),v in types.most_common()]}
(data/'record_type_migration_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('COUNT',report['total_type_changed'],'SAME_FIELD',report['same_field_exact_count'])
for r in report['by_conversion'][:15]:print(r['original_type'],'->',r['target_type'],r['field'],r['count'],'EXACT',r['same_field_exact'])
