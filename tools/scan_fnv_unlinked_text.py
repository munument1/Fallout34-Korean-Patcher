"""Scan actual FNV-converted ESM for display-text occurrences not covered by verified SST candidates."""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,struct,zlib,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
folder=root/'data'/'fnv'
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv\staging\Data\FalloutNV34.esm')
if not esm.is_file():esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\FalloutNV34.esm')
known=defaultdict(set);pairs=set()
for file in ('exact_assignments.jsonl.gz','migrated_verified_candidates.jsonl.gz'):
 for line in gzip.open(folder/file,'rt',encoding='utf-8'):
  row=json.loads(line)
  key=(int(row['target_formid'],16),row['record_type'],row['field'])
  known[key].add(row['english'])
  pairs.add((row['record_type'],row['field']))
extra={('INFO','NAM1'),('INFO','RNAM'),('TERM','ITXT'),('TERM','BTXT'),('TERM','UNAM'),('TERM','FULL'),('MESG','DESC'),('MESG','ITXT'),('MESG','FULL'),('QUST','CNAM'),('QUST','FULL'),('NPC_','FULL'),('MISC','FULL'),('WEAP','FULL'),('ARMO','FULL'),('NOTE','FULL'),('NOTE','TNAM'),('CONT','FULL'),('CELL','FULL')}
pairs.update(extra)
print('SCANNING PAIRS',len(pairs),flush=True)
def fields(b):
 i=0;extended=0;idx=Counter()
 while i+6<=len(b):
  typ,n=struct.unpack_from('<4sH',b,i);i+=6
  if typ==b'XXXX':
   if n!=4 or i+4>len(b):break
   extended=struct.unpack_from('<I',b,i)[0];i+=4;continue
  n=extended or n;extended=0
  if i+n>len(b):break
  tag=typ.decode('ascii','replace')
  idx[tag]+=1
  yield tag,idx[tag]-1,b[i:i+n]
  i+=n
def dec(raw):
 if len(raw)<3 or len(raw)>131072 or b'\0' in raw[:-1]:return None
 raw=raw.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=raw.decode(codec)
   if all(c.isprintable() or c in '\r\n\t' for c in s):return s
  except UnicodeError:pass
 return None
total=Counter();unlinked=Counter();samples=defaultdict(list);already=Counter()
file_out=folder/'unlinked_field_entries.jsonl.gz'
with esm.open('rb') as f,gzip.open(file_out,'wt',encoding='utf-8',compresslevel=6) as out:
 end=esm.stat().st_size;pos=0
 while pos<end:
  f.seek(pos);header=f.read(24)
  if len(header)!=24:raise RuntimeError('short header')
  typ,n,flags,fid,_,_=struct.unpack('<4sIIIII',header)
  if typ==b'GRUP':pos+=24;continue
  if pos+24+n>end:raise RuntimeError('bad record')
  t=typ.decode('ascii','replace')
  if any(x[0]==t for x in pairs):
   raw=f.read(n)
   if flags&0x00040000:
    expected=struct.unpack_from('<I',raw)[0]
    raw=zlib.decompress(raw[4:])
    if len(raw)!=expected:raise RuntimeError('bad zlib')
   for field,idx,blob in fields(raw):
    if (t,field) not in pairs:continue
    english=dec(blob)
    if not english or not re.search('[A-Za-z]{2}',english):continue
    total[(t,field)]+=1
    if english in known[(fid,t,field)]:
     already[(t,field)]+=1;continue
    unlinked[(t,field)]+=1
    record={'target_formid':f'{fid:08X}','record_type':t,'field':field,'target_field_occurrence_index':idx,'english':english}
    out.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
    if len(samples[(t,field)])<8:samples[(t,field)].append({'id':record['target_formid'],'english':english[:120]})
  pos+=24+n
report={'total_text_occurrences':sum(total.values()),'already_matched_occurrences':sum(already.values()),'unlinked_occurrences':sum(unlinked.values()),'by_type_field':[{'type':k[0],'field':k[1],'total':total[k],'unlinked':v,'samples':samples[k]} for k,v in unlinked.most_common()],'note':'Conservative field text scan only. Includes internal/duplicate and source-mod/generated lines. Not necessarily visible or translatable.'}
(folder/'unlinked_text_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',report['total_text_occurrences'],report['already_matched_occurrences'],report['unlinked_occurrences'],'TOP',[(r['type'],r['field'],r['unlinked']) for r in report['by_type_field'][:15]],flush=True)
