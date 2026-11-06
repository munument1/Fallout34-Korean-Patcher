"""Validate Fallout34 Korean translation candidates against actual FO4 ESM text; do not patch game files."""
from pathlib import Path
from collections import defaultdict, Counter
import hashlib,gzip,json,struct,zlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
src=root/'data'/'fo3'/'translation_candidates.jsonl.gz'
outdir=root/'data'/'fo3'
grouped=defaultdict(list)
with gzip.open(src,'rt',encoding='utf-8') as f:
 for line in f:
  r=json.loads(line)
  grouped[int(r['target_formid'],16)].append(r)
def fields(data):
 off=0;ext=0
 while off+6<=len(data):
  sig,n=struct.unpack_from('<4sH',data,off);off+=6
  if sig==b'XXXX':
   if n!=4 or off+4>len(data):break
   ext=struct.unpack_from('<I',data,off)[0];off+=4;continue
  n=ext or n;ext=0
  if off+n>len(data):break
  yield sig.decode('ascii','replace'),data[off:off+n]
  off+=n
def decode(data):
 if not data or b'\0' in data[:-1] or len(data)>65536:return None
 b=data.rstrip(b'\0')
 for name in ('utf-8','cp1252'):
  try:
   s=b.decode(name)
   if all(c.isprintable() or c in '\r\n\t' for c in s):return s
  except UnicodeDecodeError:pass
 return None
statuses=Counter();accepted=[];rejected=[]
with esm.open('rb') as f:
 end=esm.stat().st_size
 pos=0
 while pos<end:
  f.seek(pos)
  sig,size,flags,fid,revision,vc=struct.unpack('<4sIIIII',f.read(24))
  if sig==b'GRUP':pos+=24;continue
  if pos+24+size>end or size>16*1024*1024:raise ValueError('Bad record at '+str(pos))
  if fid in grouped:
   f.seek(pos+24)
   data=f.read(size)
   if flags&0x00040000:
    expected=struct.unpack_from('<I',data)[0]
    data=zlib.decompress(data[4:])
    if len(data)!=expected:raise ValueError('decompress mismatch')
   strings=defaultdict(list)
   for key,value in fields(data):
    decoded=decode(value)
    if decoded is not None:strings[key].append(decoded)
   target_type=sig.decode('ascii','replace')
   for r in grouped[fid]:
    reason=None
    if r['record_type']!=target_type:reason='record_type_changed'
    elif r['field'] not in strings:reason='field_missing'
    elif r['english'] not in strings[r['field']]:reason='english_changed'
    elif not r['korean'] or r['korean']==r['english']:reason='not_translated'
    if reason:
     r['qa_reason']=reason;rejected.append(r);statuses[reason]+=1
    else:
     accepted.append(r);statuses['exact']=statuses['exact']+1
  pos+=24+size
conflicts=defaultdict(set)
for r in accepted:
 conflicts[(r['target_formid'],r['record_type'],r['field'],r['english'])].add(r['korean'])
conflict_keys={k for k,v in conflicts.items() if len(v)>1}
unique={}
for r in accepted:
 k=(r['target_formid'],r['record_type'],r['field'],r['english'])
 if k in conflict_keys:
  r['qa_reason']='conflicting_ko_values';rejected.append(r)
 elif k not in unique:unique[k]=r
records=list(unique.values())
def dump(path,values):
 with gzip.open(path,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in values:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
dump(outdir/'verified_assignments.jsonl.gz',records)
dump(outdir/'review_needed.jsonl.gz',rejected)
h=hashlib.sha256()
with esm.open('rb') as f:
 for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
summary={'esm_size':esm.stat().st_size,'esm_sha256':h.hexdigest(),'candidate_rows':sum(map(len,grouped.values())),'matching_text_rows':len(accepted),'unique_safe_assignments':len(records),'conflicting_keys':len(conflict_keys),'review_rows':len(rejected),'qa_statuses':dict(statuses),'note':'No ESP or STRINGS has been generated. This is a version-specific read-only translation plan; do not apply without a verified FO4 patch writer.'}
(outdir/'verified_plan_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('REPORT',json.dumps(summary,ensure_ascii=True))
