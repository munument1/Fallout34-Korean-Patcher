from __future__ import annotations
import gzip,json,struct,zlib,collections
from pathlib import Path
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
unmatched=root/'data'/'fo3'/'unmatched_sst.jsonl.gz'
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
by_id=collections.defaultdict(list)
bounds=collections.Counter()
for line in gzip.open(unmatched,'rt',encoding='utf-8'):
 r=json.loads(line)
 if r['source_plugin']!='fallout3.esm':continue
 low=int(r['source_key'].split(':')[1],16)
 bounds['id_below_100000' if low<0x100000 else 'id_above_100000']+=1
 by_id[0x01000000+low].append(r)
def fields(buf):
 offset=0;ext=0
 while offset+6<=len(buf):
  tag,size=struct.unpack_from('<4sH',buf,offset);offset+=6
  if tag==b'XXXX':
   if size!=4 or offset+4>len(buf):break
   ext=struct.unpack_from('<I',buf,offset)[0];offset+=4;continue
  size=ext or size;ext=0
  if offset+size>len(buf):break
  yield tag.decode('ascii','replace'),buf[offset:offset+size]
  offset+=size
def decode(b):
 if not b or b'\0' in b[:-1] or len(b)>65536:return None
 b=b.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=b.decode(codec)
   if all(ch.isprintable() or ch in '\r\n\t' for ch in s):return s
  except UnicodeDecodeError:pass
 return None
results=collections.Counter();types=collections.Counter();sample=collections.defaultdict(list);exact=[];doubt=[]
found_ids=set()
with esm.open('rb') as f:
 size=esm.stat().st_size; pos=0
 while pos<size:
  f.seek(pos);head=f.read(24)
  typ,length,flags,fid,_,_=struct.unpack('<4sIIIII',head)
  if typ==b'GRUP':pos+=24;continue
  if fid in by_id:
   found_ids.add(fid)
   f.seek(pos+24);buf=f.read(length)
   if flags&0x00040000:
    target=struct.unpack_from('<I',buf)[0]
    buf=zlib.decompress(buf[4:])
    if len(buf)!=target:raise ValueError('Bad zlib')
   fields_map=collections.defaultdict(list)
   for tag,val in fields(buf):
    s=decode(val)
    if s is not None:fields_map[tag].append(s)
   kind=typ.decode('ascii','replace')
   for r in by_id[fid]:
    if r['record_type']!=kind: status='type_mismatch'
    elif r['field'] not in fields_map: status='field_missing'
    elif r['english'] not in fields_map[r['field']]: status='english_mismatch'
    else:status='exact'
    results[status]+=1;types[(status,r['record_type'])]+=1
    if len(sample[status])<5:
     sample[status].append({'orig':r['source_key'],'target':f'{fid:08X}','type':r['record_type'],'field':r['field'],'en':r['english'][:75],'ko':r['korean'][:75]})
    r['target_formid']=f'{fid:08X}'
    r['qa_status']=status
    (exact if status=='exact' else doubt).append(r)
  pos+=24+length
for fid,items in by_id.items():
 if fid not in found_ids:
  for r in items:
   results['id_missing']+=1;types[('id_missing',r['record_type'])]+=1
   if len(sample['id_missing'])<5:sample['id_missing'].append({'orig':r['source_key'],'target':f'{fid:08X}','type':r['record_type'],'field':r['field'],'en':r['english'][:75]})
   r['qa_status']='id_missing';doubt.append(r)
summary={'bounds':dict(bounds),'candidate_unique_ids':len(by_id),'results':dict(results),'types':types.most_common(40),'examples':dict(sample)}
out=root/'data'/'fo3'
(out/'direct_formid_probe.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with gzip.open(out/'direct_formid_exact.jsonl.gz','wt',encoding='utf-8') as fo:
 for r in exact:fo.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
with gzip.open(out/'direct_formid_review.jsonl.gz','wt',encoding='utf-8') as fo:
 for r in doubt:fo.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
print('BOUNDS',bounds)
print('UNIQUE IDS',len(by_id),'MATCHED IDS',len(found_ids))
print('RESULTS',results)
print('TYPES',types.most_common(14))
print('SAMPLES',json.dumps(sample,ensure_ascii=True)[:1300])
