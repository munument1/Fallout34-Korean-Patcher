"""Read-only compare unlinked Fallout34 strings to identical FormID in original Fallout3.esm."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,struct,zlib,hashlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
data=root/'data'/'fo3'
unmatched=data/'unmatched_field_entries.jsonl.gz'
base=Path(r'C:\Games\Steam\steamapps\common\Fallout 3 goty\Data\Fallout3.esm')
target=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm')
candidates=defaultdict(list)
original_rows=0;outside=Counter()
for line in gzip.open(unmatched,'rt',encoding='utf-8'):
 r=json.loads(line)
 fid=int(r['target_formid'],16)
 if 0x01000000<=fid<0x01100000:
  candidates[fid&0xFFFFFF].append(r)
  original_rows+=1
 else:
  outside[(r['record_type'],r['field'])]+=1
print('CANDIDATES_IN_BASE_FORMID_RANGE',original_rows,'UNIQUE_RECORD_IDS',len(candidates),'OUTSIDE_RANGE',sum(outside.values()),flush=True)
def fields(buf):
 pos=0;ext=0
 while pos+6<=len(buf):
  typ,n=struct.unpack_from('<4sH',buf,pos);pos+=6
  if typ==b'XXXX':
   if n!=4 or pos+4>len(buf):break
   ext=struct.unpack_from('<I',buf,pos)[0];pos+=4;continue
  n=ext or n;ext=0
  if pos+n>len(buf):break
  yield typ.decode('ascii','replace'),buf[pos:pos+n]
  pos+=n
def readable(raw):
 if not raw or len(raw)>131072 or b'\0' in raw[:-1]:return None
 raw=raw.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=raw.decode(codec)
   if s and all(c.isprintable() or c in '\r\n\t' for c in s):return s
  except UnicodeError:pass
 return None
stats=Counter();by_type=defaultdict(Counter);samples=defaultdict(list);hits=set()
with base.open('rb') as f:
 end=base.stat().st_size;pos=0;record_count=0
 while pos<end:
  f.seek(pos);hdr=f.read(24)
  if len(hdr)!=24:raise ValueError('short source header')
  typ,n,flags,fid,_,_=struct.unpack('<4sIIIII',hdr)
  if typ==b'GRUP':
   if n<24 or pos+n>end:raise ValueError('source bad group '+str(pos))
   pos+=24;continue
  if pos+24+n>end:raise ValueError('source record overrun '+str(pos))
  record_count+=1
  if fid in candidates:
   hits.add(fid)
   b=f.read(n)
   if flags&0x00040000:
    want=struct.unpack_from('<I',b)[0]
    b=zlib.decompress(b[4:])
    if len(b)!=want:raise RuntimeError('uncompressed mismatch')
   string_fields=defaultdict(list)
   for t,raw in fields(b):
    s=readable(raw)
    if s is not None:string_fields[t].append(s)
   rec_type=typ.decode('ascii','replace')
   for r in candidates[fid]:
    if r['record_type']!=rec_type:status='original_record_type_diff'
    elif r['english'] in string_fields[r['field']]:status='original_same_formid_field_english_exact'
    elif any(r['english'] in v for v in string_fields.values()):status='original_same_formid_other_field_english'
    elif r['field'] in string_fields:status='original_same_field_different_english'
    else:status='original_field_absent'
    stats[status]+=1;by_type[r['record_type']][status]+=1
    if len(samples[status])<12:samples[status].append({'type':r['record_type'],'field':r['field'],'target':r['target_formid'],'english':r['english'][:140],'original_record_type':rec_type,'source_field_values':[x[:120] for x in string_fields.get(r['field'],[])[:3]]})
  pos+=24+n
for fid,rs in candidates.items():
 if fid not in hits:
  for r in rs:
   stats['original_formid_missing']+=1;by_type[r['record_type']]['original_formid_missing']+=1
   if len(samples['original_formid_missing'])<12:samples['original_formid_missing'].append({'type':r['record_type'],'field':r['field'],'target':r['target_formid'],'english':r['english'][:140]})
report={'original_esm_size':base.stat().st_size,'installed_target_esm_size':target.stat().st_size,'original_records_scanned':record_count,'candidate_occurrences_in_fo3_base_range':original_rows,'outside_base_range':sum(outside.values()),'statuses':dict(stats),'by_type':{t:dict(c) for t,c in by_type.items()},'examples':dict(samples),'limitations':'Original FormID assumed from target 0x01nnnnnn for base low 0x000000–0x0FFFFF only; record type and exact English checked against actual original ESM. Not a runtime reachability test.'}
(data/'original_fo3_english_comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('ORIGINAL_RECORDS',record_count,'STATUSES',dict(stats),'TYPE INFO',dict(by_type.get('INFO',{})),flush=True)
print('EXAMPLES',json.dumps({k:v[:3] for k,v in samples.items()},ensure_ascii=True)[:2600])
