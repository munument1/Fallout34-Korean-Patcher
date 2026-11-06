"""Conservative read-only audit: scan only (record_type, field) pairs already represented by verified translations."""
from collections import Counter,defaultdict
from pathlib import Path
import gzip, json, re, struct, zlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
data=root/'data'/'fo3'
translations=defaultdict(set)
known_pairs=set()
with gzip.open(data/'verified_assignments_all.jsonl.gz','rt',encoding='utf-8') as source:
 for line in source:
  r=json.loads(line)
  typ=r['record_type'];field=r['field'];fid=int(r['target_formid'],16)
  translations[(fid,typ,field)].add(r['english'])
  known_pairs.add((typ,field))
print('KNOWN TYPE/FIELD PAIRS',len(known_pairs),flush=True)
def fields(data):
 i=0;extended=0
 while i+6<=len(data):
  sig,n=struct.unpack_from('<4sH',data,i);i+=6
  if sig==b'XXXX':
   if n!=4 or i+4>len(data):break
   extended=struct.unpack_from('<I',data,i)[0];i+=4;continue
  n=extended or n;extended=0
  if i+n>len(data):break
  yield sig.decode('ascii','replace'),data[i:i+n]
  i+=n
def readable(data):
 if len(data)<4 or len(data)>131072 or b'\0' in data[:-1]:return None
 data=data.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   text=data.decode(codec)
   if text and all(c.isprintable() or c in '\r\n\t' for c in text):return text
  except UnicodeError:pass
 return None
total=Counter();unknown=Counter();sample=defaultdict(list);found_set=set();top_examples=Counter()
unmatched_records=[]
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
with esm.open('rb') as stream:
 end=esm.stat().st_size;pos=0
 while pos<end:
  stream.seek(pos);rec=stream.read(24)
  if len(rec)!=24:raise RuntimeError('record header')
  typ,size,flags,fid,_,_=struct.unpack('<4sIIIII',rec)
  if typ==b'GRUP':pos+=24;continue
  rec_type=typ.decode('ascii','replace')
  if any(r==rec_type for r,_ in known_pairs):
   b=stream.read(size)
   if flags&0x00040000:
    expected=struct.unpack_from('<I',b)[0]
    b=zlib.decompress(b[4:])
    if len(b)!=expected:raise RuntimeError('inflate mismatch')
   for field,v in fields(b):
    if (rec_type,field) not in known_pairs:continue
    text=readable(v)
    if not text or not re.search('[a-zA-Z]{2}',text):continue
    if len(text.strip())<3:continue
    k=(rec_type,field)
    total[k]+=1
    if text not in translations.get((fid,rec_type,field),set()):
     unknown[k]+=1
     unmatched_records.append({'target_formid':f'{fid:08X}','record_type':rec_type,'field':field,'english':text})
     if len(sample[k])<14:
      sample[k].append({'formid':f'{fid:08X}','english':text[:180]})
  pos+=24+size
rank=unknown.most_common(50)
report={'inspection_scope':'Only record type/field pairs already represented in verified SST translations; not exhaustive','pairs_scanned':len(known_pairs),'total_text_occurrences':sum(total.values()),'unmatched_text_occurrences':sum(unknown.values()),'unmatched_by_pair':[{'record_type':k[0],'field':k[1],'total_text_occurrences':total[k],'unmatched_text_occurrences':v,'examples':sample[k]} for k,v in rank],'warning':'Unmatched strings are candidates for review, not confirmed game-visible untranslated text. They can be generated, duplicated, inherited from mods, internal, or require special handling.'}
with gzip.open(data/'unmatched_field_entries.jsonl.gz','wt',encoding='utf-8',compresslevel=6) as f:
 for row in unmatched_records:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
(data/'unmatched_display_text_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('TOTAL FIELDS',report['total_text_occurrences'],'UNMATCHED',report['unmatched_text_occurrences'])
for row in report['unmatched_by_pair'][:20]:print('TYPE',row['record_type'],row['field'],'TOTAL',row['total_text_occurrences'],'MISSING',row['unmatched_text_occurrences'],'EX',[(x['formid'],x['english'][:60]) for x in row['examples'][:3]])
