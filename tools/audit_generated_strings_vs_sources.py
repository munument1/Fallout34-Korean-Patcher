"""Read-only original ESM search for every unlinked English text in generated FO4 Fallout34 ESM."""
from pathlib import Path
from collections import defaultdict, Counter
import gzip, json, struct, zlib, re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
data=root/'data'/'fo3'
native=Path(r'C:\Games\Steam\steamapps\common\Fallout 3 goty\Data')
sources=['Fallout3.esm','Anchorage.esm','ThePitt.esm','BrokenSteel.esm','PointLookout.esm','Zeta.esm']
all_candidates=[]
by_text=defaultdict(list)
for line in gzip.open(data/'unmatched_field_entries.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 all_candidates.append(r)
 by_text[r['english']].append(len(all_candidates)-1)
def fields(raw):
 pos=0;extended=0
 while pos+6<=len(raw):
  typ,n=struct.unpack_from('<4sH',raw,pos);pos+=6
  if typ==b'XXXX':
   if n!=4 or pos+4>len(raw):break
   extended=struct.unpack_from('<I',raw,pos)[0];pos+=4;continue
  n=extended or n;extended=0
  if pos+n>len(raw):break
  yield typ.decode('ascii','replace'),raw[pos:pos+n]
  pos+=n
def decoded_text(raw):
 if len(raw)<4 or len(raw)>131072 or b'\0' in raw[:-1]:return None
 raw=raw.rstrip(b'\0')
 for encoding in ('utf-8','cp1252'):
  try:
   value=raw.decode(encoding)
   if value and all(c.isprintable() or c in '\r\n\t' for c in value):return value
  except UnicodeError:pass
 return None
hits=defaultdict(list); source_counts=Counter(); scan_counts=Counter();needed=set(by_text)
for plugin in sources:
 file=native/plugin
 print('SOURCE',plugin,'size',file.stat().st_size,flush=True)
 with file.open('rb') as f:
  end=file.stat().st_size;pos=0
  while pos<end:
   f.seek(pos);header=f.read(24)
   if len(header)!=24:raise RuntimeError('Truncated source '+plugin)
   typ,size,flags,formid,_,_=struct.unpack('<4sIIIII',header)
   if typ==b'GRUP':
    if size<24 or pos+size>end:raise RuntimeError('Bad group')
    pos+=24;continue
   if pos+24+size>end:raise RuntimeError('Bad record')
   scan_counts[plugin]+=1
   # Parse only the types likely to have display text. Includes all source types known to SST and conversion.
   if typ in (b'INFO',b'DIAL',b'TERM',b'NOTE',b'NPC_',b'CREA',b'QUST',b'MESG',b'MISC',b'CONT',b'BOOK',b'LSCR',b'PERK',b'WEAP',b'ARMO',b'ACTI',b'FURN',b'DOOR',b'FACT',b'CELL',b'SPEL',b'MGEF',b'ENCH',b'KEYM',b'CLAS',b'AMMO',b'RACE',b'MSTT',b'REFR',b'WRLD',b'ALCH',b'TACT',b'EXPL',b'ACHR',b'INGR',b'PROJ',b'FLOR',b'PACK',b'WATR',b'REGN'):
    f.seek(pos+24)
    raw=f.read(size)
    if flags&0x00040000:
     if len(raw)<4:raise RuntimeError('Short compressed')
     want=struct.unpack_from('<I',raw)[0]
     raw=zlib.decompress(raw[4:])
     if len(raw)!=want:raise RuntimeError('Invalid compression')
    subs=Counter()
    for field,part in fields(raw):
     value=decoded_text(part)
     if value is None:continue
     index=subs[field];subs[field]+=1
     if value in needed:
      source_counts[plugin]+=1
      hits[value].append({'plugin':plugin.lower(),'local_id':f'{formid&0xffffff:06x}','record_type':typ.decode('ascii','replace'),'field':field,'sub_index':index})
   pos+=24+size
 print('FINISHED',plugin,'records',scan_counts[plugin],'matched_source_subrecords',source_counts[plugin],flush=True)
by_form=defaultdict(Counter);overall=Counter();samples=defaultdict(list);unique_original=Counter()
out_hits=data/'generated_source_match_candidates.jsonl.gz'
with gzip.open(out_hits,'wt',encoding='utf-8',compresslevel=6) as output:
 for r in all_candidates:
  arr=hits.get(r['english'],[])
  same_type_field=[x for x in arr if x['record_type']==r['record_type'] and x['field']==r['field']]
  same_type=[x for x in arr if x['record_type']==r['record_type']]
  if same_type_field: status='same_type_field_in_original';best=same_type_field
  elif same_type:status='same_type_other_field_in_original';best=same_type
  elif arr:status='different_type_in_original';best=arr
  else:status='no_english_in_original_ESMs';best=[]
  overall[status]+=1;by_form[r['record_type']][status]+=1
  if len(samples[status])<10:samples[status].append({'formid':r['target_formid'],'record_type':r['record_type'],'field':r['field'],'english':r['english'][:95],'sources':best[:3]})
  if best and status=='same_type_field_in_original':
   unique_original[len(best)]+=1
  if best:
   record=dict(r);record['status']=status;record['source_candidates_count']=len(best);record['source_candidates']=best[:30]
   output.write(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n')
report={'total_unmatched_occurrences':len(all_candidates),'unique_english_strings':len(by_text),'source_files':sources,'source_scan_records':dict(scan_counts),'source_matched_subrecords':dict(source_counts),'status':dict(overall),'by_target_record_type':{k:dict(v) for k,v in by_form.items()},'source_candidates_per_matching_text':dict(unique_original.most_common(20)),'examples':dict(samples),'limitation':'Exact English present in original source is not proof of same in-game context. Candidate count capped at 30 for output; no patch applied.'}
(data/'generated_original_source_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',dict(overall),'INFO',dict(by_form.get('INFO',{})),'TERM',dict(by_form.get('TERM',{})),flush=True)
print('ORIGINAL MATCH COUNTS',unique_original.most_common(12),flush=True)
print('EXAMPLES',json.dumps({k:v[:3] for k,v in samples.items()},ensure_ascii=True)[:2500],flush=True)
