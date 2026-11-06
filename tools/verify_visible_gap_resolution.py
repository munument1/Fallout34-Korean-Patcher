"""Independently verify every new strict translation assignment in its source ESM, without modifying ESM."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,hashlib,struct,zlib
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
FO4=Path(r'C:\Games\Steam\steamapps\common\Fallout 4')
def fields(data):
 pos=0;ext=0;count=Counter()
 while pos+6<=len(data):
  tag,n=struct.unpack_from('<4sH',data,pos);pos+=6
  if tag==b'XXXX':
   if n!=4 or pos+4>len(data):break
   ext=struct.unpack_from('<I',data,pos)[0];pos+=4;continue
  n=ext or n;ext=0
  if pos+n>len(data):break
  field=tag.decode('ascii','replace');i=count[field];count[field]+=1
  yield field,i,data[pos:pos+n]
  pos+=n
def decode(data):
 if len(data)<2 or len(data)>131072 or b'\0' in data[:-1]:return None
 b=data.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=b.decode(codec)
   if all(c.isprintable() or c in '\r\n\t' for c in s):return s
  except UnicodeError:pass
 return None
for game in ('fo3','fnv'):
 d=ROOT/'data'/game
 esm=FO4/'Data'/('Fallout34.esm' if game=='fo3' else 'FalloutNV34.esm')
 if game=='fnv' and not esm.exists():esm=FO4/'Fallout34_Work'/'fnv'/'staging'/'Data'/'FalloutNV34.esm'
 report=json.loads((d/'indexed_plan_report.json').read_text(encoding='utf-8'))
 by_id=defaultdict(list);keys=set()
 for line in gzip.open(d/'indexed_patch_plan_v2_strict_extra.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line);k=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'])
  if k in keys:raise RuntimeError('Duplicate strict target: '+str(k))
  keys.add(k);by_id[int(r['target_formid'],16)].append(r)
 print('SCAN',game,'TOTAL',len(keys),'TARGET_RECORDS',len(by_id),flush=True)
 result=Counter();samples=defaultdict(list)
 start=esm.stat()
 with esm.open('rb') as f:
  pos=0;end=start.st_size
  while pos<end:
   f.seek(pos);h=f.read(24)
   if len(h)!=24:raise ValueError('truncated header')
   tag,size,flags,fid,_,_=struct.unpack('<4sIIIII',h)
   if tag==b'GRUP':pos+=24;continue
   if size>16*1024*1024 or pos+24+size>end:raise RuntimeError('invalid record')
   if fid in by_id:
    raw=f.read(size)
    if flags&0x00040000:
     expected=struct.unpack_from('<I',raw)[0];raw=zlib.decompress(raw[4:])
     if len(raw)!=expected:raise ValueError('bad compressed record')
    typ=tag.decode('ascii','replace')
    indexed={(name,idx):decode(blob) for name,idx,blob in fields(raw)}
    for r in by_id.pop(fid):
     if typ!=r['record_type']:state='record_type_changed'
     elif indexed.get((r['field'],int(r['target_field_occurrence_index'])))!=r['english']:state='target_field_english_changed'
     else:state='byte_provenance_validated'
     result[state]+=1
     if state!='byte_provenance_validated' and len(samples[state])<5:samples[state].append(r)
   pos+=24+size
 if by_id:result['target_formid_missing']=sum(map(len,by_id.values()))
 h=hashlib.sha256()
 with esm.open('rb') as f:
  for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
 if esm.stat().st_size!=start.st_size or esm.stat().st_mtime_ns!=start.st_mtime_ns:raise RuntimeError('ESM changed')
 if h.hexdigest()!=report['esm_sha256']:raise RuntimeError('ESM hash mismatch')
 if result['byte_provenance_validated']!=len(keys):raise RuntimeError('Source mismatch! '+repr(result))
 output={'game':game,'source_esm_sha256':h.hexdigest(),'strict_extra_assignments':len(keys),'verified_exact_record_type_field_occurrence_english':result['byte_provenance_validated'],'issues':{k:v for k,v in result.items() if k!='byte_provenance_validated'},'status':'pass; not installed or tested in-game'}
 (d/'strict_extra_esm_verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PASS',game,output,flush=True)
