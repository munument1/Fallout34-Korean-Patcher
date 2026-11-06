"""Recover only unmapped FO3 DLC SST rows, using modal offsets verified from source mapping."""
from pathlib import Path
import csv,gzip,json,struct,zlib,collections
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
fo3=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3')
source=fo3/'work'/'reports'/'formid_map.tsv'
deltas=collections.defaultdict(collections.Counter)
with source.open('r',encoding='utf-8') as f:
 for r in csv.DictReader(f,delimiter='\t'):
  try:
   plugin,low=r['source'].casefold().split(':',1)
   if plugin in ('anchorage.esm','thepitt.esm','brokensteel.esm','pointlookout.esm','zeta.esm'):
    deltas[plugin][int(r['formid'],16)-int(low,16)]+=1
  except Exception:pass
offsets={p:c.most_common(1)[0][0] for p,c in deltas.items()}
counts={p:c.most_common(2) for p,c in deltas.items()}
print('OFFSETS',offsets,'COUNTS',counts)
by_id=collections.defaultdict(list)
for line in gzip.open(root/'data'/'fo3'/'unmatched_sst.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 plugin=r['source_plugin']
 if plugin not in offsets:continue
 low=int(r['source_key'].split(':',1)[1],16)
 r['target_formid']=f'{offsets[plugin]+low:08X}'
 r['mapping_method']='dlc_modal_offset_validated_by_esm_text'
 by_id[int(r['target_formid'],16)].append(r)
def fields(buf):
 pos=0;ext=0
 while pos+6<=len(buf):
  sig,size=struct.unpack_from('<4sH',buf,pos);pos+=6
  if sig==b'XXXX':
   if size!=4 or pos+4>len(buf):break
   ext=struct.unpack_from('<I',buf,pos)[0];pos+=4;continue
  size=ext or size;ext=0
  if pos+size>len(buf):break
  yield sig.decode('ascii','replace'),buf[pos:pos+size];pos+=size
def decode(b):
 if not b or b'\0' in b[:-1] or len(b)>65536:return None
 b=b.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=b.decode(codec)
   if all(c.isprintable() or c in '\r\n\t' for c in s):return s
  except UnicodeError:pass
 return None
seen=set();passed=[];review=[];statuses=collections.Counter()
esm=fo3/'staging'/'Data'/'Fallout34.esm'
with esm.open('rb') as f:
 end=esm.stat().st_size;pos=0
 while pos<end:
  f.seek(pos);sig,size,flags,fid,_,_=struct.unpack('<4sIIIII',f.read(24))
  if sig==b'GRUP':pos+=24;continue
  if pos+24+size>end:raise RuntimeError('invalid ESM')
  if fid in by_id:
   seen.add(fid)
   f.seek(pos+24);buf=f.read(size)
   if flags&0x00040000:
    uncompressed=struct.unpack_from('<I',buf)[0]
    buf=zlib.decompress(buf[4:])
    if len(buf)!=uncompressed:raise RuntimeError('zlib length mismatch')
   field_dict=collections.defaultdict(list)
   for k,v in fields(buf):
    s=decode(v)
    if s is not None:field_dict[k].append(s)
   typ=sig.decode('ascii','replace')
   for r in by_id[fid]:
    if r['record_type']!=typ:reason='type_mismatch'
    elif r['field'] not in field_dict:reason='field_missing'
    elif r['english'] not in field_dict[r['field']]:reason='english_mismatch'
    else:reason='exact'
    statuses[reason]+=1
    (passed if reason=='exact' else review).append(r)
  pos+=24+size
for fid,rs in by_id.items():
 if fid not in seen:
  review.extend(rs);statuses['id_missing']+=len(rs)
out=root/'data'/'fo3'
def write(name,rs):
 with gzip.open(out/name,'wt',encoding='utf-8') as f:
  for r in rs:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
write('dlc_direct_exact.jsonl.gz',passed);write('dlc_direct_review.jsonl.gz',review)
report={'modal_offsets':{k:hex(v) for k,v in offsets.items()},'modal_counts':{k:v.most_common(1)[0][1] for k,v in deltas.items()},'results':dict(statuses)}
(out/'dlc_direct_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',dict(statuses))
