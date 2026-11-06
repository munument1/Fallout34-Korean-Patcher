"""Read-only exact-match validation for FalloutNV34 ESM against translated SST rows."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,struct,zlib,hashlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher');out=root/'data'/'fnv'
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv\staging\Data\FalloutNV34.esm')
if not esm.exists():
 esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\FalloutNV34.esm')
by_id=defaultdict(list);no_id_count=0
for line in gzip.open(out/'formid_candidates.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line);by_id[int(r['target_formid'],16)].append(r)
print('TARGET RECORD IDS',len(by_id),'candidate rows',sum(len(v) for v in by_id.values()),'ESM',esm,flush=True)
start=esm.stat();target_size=start.st_size
def fields(blob):
 i=0;ext=0
 while i+6<=len(blob):
  name,n=struct.unpack_from('<4sH',blob,i);i+=6
  if name==b'XXXX':
   if n!=4 or i+4>len(blob):break
   ext=struct.unpack_from('<I',blob,i)[0];i+=4;continue
  n=ext or n;ext=0
  if i+n>len(blob):break
  yield name.decode('ascii','replace'),blob[i:i+n]
  i+=n
def text(v):
 if not v or len(v)>131072 or b'\0' in v[:-1]:return None
 b=v.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   t=b.decode(codec)
   if all(c.isprintable() or c in '\r\n\t' for c in t):return t
  except UnicodeError:pass
 return None
seen=set();passes=[];reject=[];reasons=Counter();per_source=defaultdict(Counter)
hashing=hashlib.sha256();records_scanned=0
with esm.open('rb') as f:
 pos=0
 while pos<target_size:
  f.seek(pos);header=f.read(24)
  if len(header)!=24:raise ValueError('truncated record header')
  name,n,flags,fid,revision,misc=struct.unpack('<4sIIIII',header)
  if name==b'GRUP':
   if n<24 or pos+n>target_size:raise ValueError('bad GRUP '+str(pos))
   pos+=24;continue
  if pos+24+n>target_size or n>16*1024*1024:raise ValueError('bad record')
  records_scanned+=1
  if fid in by_id:
   seen.add(fid)
   raw=f.read(n)
   if flags&0x00040000:
    if len(raw)<4:raise ValueError('compressed header')
    expected=struct.unpack_from('<I',raw)[0]
    raw=zlib.decompress(raw[4:])
    if len(raw)!=expected:raise ValueError('zlib length')
   ff=defaultdict(list)
   for tag,b in fields(raw):
    s=text(b)
    if s is not None:ff[tag].append(s)
   typ=name.decode('ascii','replace')
   for r in by_id[fid]:
    if r['record_type']!=typ:reason='type_changed'
    elif r['field'] not in ff:reason='field_absent'
    elif r['english'] not in ff[r['field']]:reason='english_changed'
    else:reason='text_exact'
    r['validation_status']=reason
    reasons[reason]+=1;per_source[r['source_plugin']][reason]+=1
    (passes if reason=='text_exact' else reject).append(r)
  pos+=24+n
for fid,rs in by_id.items():
 if fid not in seen:
  for r in rs:r['validation_status']='target_id_absent';reasons['target_id_absent']+=1;per_source[r['source_plugin']]['target_id_absent']+=1;reject.append(r)
# Multi-valued field with identical English but differing Korean cannot be blindly assigned to each occurrence.
indexed=defaultdict(set)
for r in passes:
 indexed[(r['target_formid'],r['record_type'],r['field'],r['english'])].add(r['korean'])
conflicting={k for k,v in indexed.items() if len(v)>1}
strong=[];excluded_conflicts=[]
unique={}
for r in passes:
 key=(r['target_formid'],r['record_type'],r['field'],r['english'])
 if key in conflicting:
  excluded_conflicts.append(r);continue
 if key not in unique:unique[key]=r
strong=list(unique.values())
def save(name,rows):
 with gzip.open(out/name,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
save('exact_assignments.jsonl.gz',strong);save('review_needed.jsonl.gz',reject+excluded_conflicts)
hashing=hashlib.sha256()
with esm.open('rb') as f:
 for chunk in iter(lambda:f.read(8*1024*1024),b''):hashing.update(chunk)
if esm.stat().st_size!=target_size or esm.stat().st_mtime_ns!=start.st_mtime_ns:raise RuntimeError('ESM CHANGED during verification; do not rely on report')
report={'source_esm':str(esm),'esm_bytes':target_size,'esm_sha256':hashing.hexdigest(),'records_scanned':records_scanned,'candidate_records':sum(len(v) for v in by_id.values()),'reason_counts':dict(reasons),'per_source':{s:dict(c) for s,c in per_source.items()},'exact_unique_assignments':len(strong),'duplicated_rows':len(passes)-len(strong)-len(excluded_conflicts),'english_to_korean_conflict_keys':len(conflicting),'conflict_excluded_rows':len(excluded_conflicts),'needs_review_rows':len(reject)+len(excluded_conflicts),'limitations':'FO4 ESM text and record type/field verified. INFO response index, multiple string field occurrences, and runtime display/record dependencies not yet verified. Do not overwrite ESM.'}
(out/'verification_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',json.dumps({k:v for k,v in report.items() if k not in ('source_esm','per_source','limitations')},ensure_ascii=True),flush=True)
print('SOURCE_STATS',json.dumps(report['per_source'],ensure_ascii=True)[:2200])
