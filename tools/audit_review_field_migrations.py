"""Read-only: look for rejected SST English in changed FO4 fields, never auto-patch."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,struct,zlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
dir=root/'data'/'fo3'
target=defaultdict(list)
review_files=['review_needed.jsonl.gz','direct_formid_review.jsonl.gz','dlc_direct_review.jsonl.gz']
missing=Counter();rows=0
for file in review_files:
 for line in gzip.open(dir/file,'rt',encoding='utf-8'):
  row=json.loads(line);rows+=1
  if 'target_formid' not in row:missing[file]+=1;continue
  target[int(row['target_formid'],16)].append(row)
def fields(blob):
 i=0;extended=0
 while i+6<=len(blob):
  tag,n=struct.unpack_from('<4sH',blob,i);i+=6
  if tag==b'XXXX':
   if n!=4 or i+4>len(blob):break
   extended=struct.unpack_from('<I',blob,i)[0];i+=4;continue
  n=extended or n;extended=0
  if i+n>len(blob):break
  yield tag.decode('ascii','replace'),blob[i:i+n];i+=n
def decode(raw):
 if not raw or len(raw)>131072 or b'\0' in raw[:-1]:return None
 raw=raw.rstrip(b'\0')
 for encoding in ('utf-8','cp1252'):
  try:
   text=raw.decode(encoding)
   if text and all(c.isprintable() or c in '\r\n\t' for c in text):return text
  except UnicodeError:pass
 return None
classifications=Counter();bytype=Counter();byfield=Counter();example=defaultdict(list);matches=[]
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
with esm.open('rb') as f:
 size=esm.stat().st_size;pos=0
 while pos<size:
  f.seek(pos)
  typ,n,flags,fid,_,_=struct.unpack('<4sIIIII',f.read(24))
  if typ==b'GRUP':pos+=24;continue
  if pos+24+n>size:raise ValueError('out-of-bounds')
  if fid in target:
   f.seek(pos+24);blob=f.read(n)
   if flags&0x00040000:
    expected=struct.unpack_from('<I',blob)[0]
    blob=zlib.decompress(blob[4:])
    if len(blob)!=expected:raise ValueError('decompressed size mismatch')
   strings=defaultdict(list)
   for tag,raw in fields(blob):
    val=decode(raw)
    if val is not None:strings[tag].append(val)
   rec_typ=typ.decode('ascii','replace')
   for row in target[fid]:
    orig_type=row['record_type'];orig_field=row['field'];eng=row['english']
    matching_fields=[t for t,vals in strings.items() if eng in vals]
    if orig_type!=rec_typ:
     status='record_type_changed'
    elif orig_field in matching_fields:
     status='same_field_found'
    elif matching_fields:
     status='other_field_exact'
    elif orig_field not in strings:
     status='field_absent_no_exact_text'
    else:
     status='english_changed'
    classifications[status]+=1;bytype[(status,orig_type)]+=1;byfield[(status,orig_field)]+=1
    if len(example[status])<8:example[status].append({'source':row['source_key'],'target':row['target_formid'],'type':orig_type,'field':orig_field,'matching_fields':matching_fields,'en':eng[:90],'ko':row['korean'][:90],'available_fields':list(strings)[:16]})
    if status=='other_field_exact':matches.append({'row':row,'matching_fields':matching_fields})
  pos+=24+n
print('review_rows',rows,'without_target_formid',missing)
print('CLASSES',classifications,'TOP',bytype.most_common(20))
print('EXAMPLES',json.dumps(dict(example),ensure_ascii=True)[:3400])
report={'total_review_rows':rows,'missing_formid_in_review':dict(missing),'statuses':dict(classifications),'by_type':[(list(k),v) for k,v in bytype.most_common()],'examples':dict(example),'note':'Matches in other fields are REVIEW ONLY, not safely reassignable because FO4 schemas and INFO indexing differ.'}
(dir/'field_migration_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with gzip.open(dir/'possible_field_migrations.jsonl.gz','wt',encoding='utf-8') as f:
 for item in matches:f.write(json.dumps(item,ensure_ascii=False,separators=(',',':'))+'\n')
