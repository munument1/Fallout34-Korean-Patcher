"""Validate migrated source record type/field against actual converted ESM without writing game files."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse,gzip,hashlib,json,struct,zlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
def scan_fields(buf):
 pos=0;ext=0;index=Counter()
 while pos+6<=len(buf):
  typ,n=struct.unpack_from('<4sH',buf,pos);pos+=6
  if typ==b'XXXX':
   if n!=4 or pos+4>len(buf):break
   ext=struct.unpack_from('<I',buf,pos)[0];pos+=4;continue
  n=ext or n;ext=0
  if pos+n>len(buf):break
  tag=typ.decode('ascii','replace')
  index[tag]+=1
  yield tag,index[tag]-1,buf[pos:pos+n]
  pos+=n
def decode(raw):
 if not raw or len(raw)>131072 or b'\0' in raw[:-1]:return None
 b=raw.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=b.decode(codec)
   if all(ch.isprintable() or ch in '\r\n\t' for ch in s):return s
  except UnicodeError:pass
 return None
def run(game):
 folder=root/'data'/game
 source=['review_needed.jsonl.gz'] if game=='fnv' else ['review_needed.jsonl.gz','direct_formid_review.jsonl.gz','dlc_direct_review.jsonl.gz']
 esm=(Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv\staging\Data\FalloutNV34.esm') if game=='fnv' else Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm'))
 if not esm.is_file() and game=='fnv':esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\FalloutNV34.esm')
 by_id=defaultdict(list);no_id=0
 for name in source:
  with gzip.open(folder/name,'rt',encoding='utf-8') as f:
   for line in f:
    row=json.loads(line)
    if 'target_formid' not in row:no_id+=1;continue
    by_id[int(row['target_formid'],16)].append(row)
 print('GAME',game,'target ids',len(by_id),'rows',sum(map(len,by_id.values())),'ESM',esm,flush=True)
 statuses=Counter();samples=defaultdict(list);passed=[];review=[];type_conversion=Counter();field_conversion=Counter()
 seen=set();start=esm.stat()
 with esm.open('rb') as f:
  end=start.st_size;pos=0
  while pos<end:
   f.seek(pos);head=f.read(24)
   if len(head)!=24:raise ValueError('Truncated record header')
   typ,size,flags,fid,_,_=struct.unpack('<4sIIIII',head)
   if typ==b'GRUP':pos+=24;continue
   if pos+24+size>end or size>16*1024*1024:raise ValueError('Bad record '+str(pos))
   if fid in by_id:
    seen.add(fid)
    buf=f.read(size)
    if flags&0x00040000:
     length=struct.unpack_from('<I',buf)[0]
     buf=zlib.decompress(buf[4:])
     if len(buf)!=length:raise RuntimeError('Zlib mismatch')
    fields=defaultdict(list)
    for tag,index,raw in scan_fields(buf):
     text=decode(raw)
     if text is not None:fields[tag].append((index,text))
    target_type=typ.decode('ascii','replace')
    for r in by_id[fid]:
     all_matches=[(tag,index) for tag,items in fields.items() for index,t in items if t==r['english']]
     same_field=[(tag,index) for tag,index in all_matches if tag==r['field']]
     if len(all_matches)==0:
      status='no_exact_english_in_record';newfield=None
     elif target_type!=r['record_type'] and len(same_field)==1:
      status='type_migration_exact_unique';newfield=r['field'];type_conversion[(r['record_type'],target_type)]+=1
     elif target_type==r['record_type'] and len(same_field)==1:
      status='same_field_exact_unique';newfield=r['field']
     elif target_type==r['record_type'] and len(all_matches)==1:
      status='field_migration_exact_unique';newfield=all_matches[0][0];field_conversion[(r['record_type'],r['field'],newfield)]+=1
     elif target_type!=r['record_type'] and len(all_matches)==1:
      status='type_and_field_migration_exact_unique';newfield=all_matches[0][0]
     else:status='ambiguous_duplicate_text';newfield=None
     statuses[status]+=1
     if len(samples[status])<5:samples[status].append({'source':r['source_key'],'target':r['target_formid'],'old_type':r['record_type'],'old_field':r['field'],'new_type':target_type,'new_field':newfield,'english':r['english'][:85],'matches':all_matches[:8]})
     if newfield and status not in ('ambiguous_duplicate_text','no_exact_english_in_record'):
      record=dict(r);record['original_record_type']=r['record_type'];record['original_field']=r['field'];record['record_type']=target_type;record['field']=newfield;record['migration_status']=status
      record['target_field_occurrence_index']=(same_field if newfield==r['field'] else all_matches)[0][1]
      passed.append(record)
     else:review.append(r)
   pos+=24+size
 for fid,rs in by_id.items():
  if fid not in seen:
   statuses['missing_record']+=len(rs);review.extend(rs)
 # Group by new type, field, English, occurrence, FormID; exclude conflicting Korean.
 by_key=defaultdict(set)
 for r in passed:
  k=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'],r['english'])
  by_key[k].add(r['korean'])
 conflict={k for k,vals in by_key.items() if len(vals)!=1}
 unique={}
 for r in passed:
  k=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'],r['english'])
  if k in conflict:review.append(r);continue
  unique.setdefault(k,r)
 def save(name,items):
  with gzip.open(folder/name,'wt',encoding='utf-8',compresslevel=6) as f:
   for r in items:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
 save('migrated_verified_candidates.jsonl.gz',unique.values())
 save('migrated_still_review.jsonl.gz',review)
 sha=hashlib.sha256()
 with esm.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):sha.update(b)
 if esm.stat().st_size!=start.st_size or esm.stat().st_mtime_ns!=start.st_mtime_ns:raise RuntimeError('Source ESM modified during scan')
 report={'game':game,'esm_sha256':sha.hexdigest(),'reviewed_source_rows':sum(map(len,by_id.values()))+no_id,'source_without_target_id':no_id,'statuses':dict(statuses),'migration_candidates_unique':len(unique),'translation_conflicts':len(conflict),'type_conversions':[(list(k),v) for k,v in type_conversion.most_common()],'field_conversions':[(list(k),v) for k,v in field_conversion.most_common()],'samples':dict(samples),'warning':'Exact text and target field occurrence verified; contextual source connection, native FO4 plugin writer and ingame testing are still needed.'}
 (folder/'migrated_verification_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('RESULT',game,json.dumps({k:v for k,v in report.items() if k not in ('type_conversions','field_conversions','samples','warning')},ensure_ascii=True),'TYPES',type_conversion.most_common(15),'FIELDS',field_conversion.most_common(10),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('game',choices=['fo3','fnv']);args=parser.parse_args();run(args.game)
