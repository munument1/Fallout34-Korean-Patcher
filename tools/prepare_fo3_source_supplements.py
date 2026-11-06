"""Prioritize FO3 unlinked text whose original ESM record type/field and SST Korean agree."""
from collections import defaultdict,Counter
from pathlib import Path
import gzip,json,struct,zlib,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
out=root/'data'/'fo3'
by_id=defaultdict(list);source_counts=Counter()
for file in ('original_translation_strong_candidates.jsonl.gz','original_translation_review_candidates.jsonl.gz'):
 for line in gzip.open(out/file,'rt',encoding='utf-8'):
  r=json.loads(line)
  if r['match_class'] not in ('single_original_record_and_translated','multiple_original_records_same_korean'):continue
  if r['status']!='same_type_field_in_original' or 'possible_korean' not in r:continue
  by_id[int(r['target_formid'],16)].append(r);source_counts[r['match_class']]+=1
print('STAGED',sum(map(len,by_id.values())),source_counts,flush=True)
def fields(b):
 p=0;ext=0;index=Counter()
 while p+6<=len(b):
  sig,n=struct.unpack_from('<4sH',b,p);p+=6
  if sig==b'XXXX':
   if n!=4 or p+4>len(b):break
   ext=struct.unpack_from('<I',b,p)[0];p+=4;continue
  n=ext or n;ext=0
  if p+n>len(b):break
  tag=sig.decode('ascii','replace');index[tag]+=1
  yield tag,index[tag]-1,b[p:p+n];p+=n
def dec(v):
 if not v or len(v)>131072 or b'\0' in v[:-1]:return None
 v=v.rstrip(b'\0')
 for c in ('utf-8','cp1252'):
  try:
   s=v.decode(c)
   if all(x.isprintable() or x in '\t\r\n' for x in s):return s
  except UnicodeError:pass
 return None
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm')
status=Counter();staged=[];review=[];seen=set()
with esm.open('rb') as f:
 end=esm.stat().st_size;pos=0
 while pos<end:
  f.seek(pos);head=f.read(24)
  typ,n,flags,fid,_,_=struct.unpack('<4sIIIII',head)
  if typ==b'GRUP':pos+=24;continue
  if fid in by_id:
   seen.add(fid);b=f.read(n)
   if flags&0x00040000:
    size=struct.unpack_from('<I',b)[0];b=zlib.decompress(b[4:])
    if len(b)!=size:raise RuntimeError('zlib')
   strings=defaultdict(list)
   for tag,index,raw in fields(b):
    text=dec(raw)
    if text is not None:strings[tag].append((index,text))
   new_type=typ.decode('ascii','replace')
   for r in by_id[fid]:
    matches=[i for i,t in strings.get(r['field'],[]) if t==r['english']]
    if new_type!=r['record_type']:reason='record_type_mismatch'
    elif len(matches)!=1:reason='ambiguous_or_no_exact_field_text'
    else:reason='candidate_match'
    status[reason]+=1
    if reason=='candidate_match':
     rr={'target_formid':r['target_formid'],'record_type':r['record_type'],'field':r['field'],'target_field_occurrence_index':matches[0],'english':r['english'],'korean':r['possible_korean'],'match_class':r['match_class'],'original_sources':r['source_candidates'],'source_candidates_count':r['source_candidates_count']}
     staged.append(rr)
    else:review.append(r)
  pos+=24+n
for fid,rs in by_id.items():
 if fid not in seen:status['target_record_missing']+=len(rs);review.extend(rs)
pattern=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}')
verified=[];conflict_keys=defaultdict(set)
for r in staged:
 key=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'])
 conflict_keys[key].add(r['korean'])
disagree={k for k,v in conflict_keys.items() if len(v)!=1}
seen_keys=set()
for r in staged:
 key=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'])
 if key in disagree:reason='ko_conflict'
 elif Counter(pattern.findall(r['english']))!=Counter(pattern.findall(r['korean'])):reason='markup_mismatch'
 elif key in seen_keys:reason='duplicate'
 else:reason='candidate'
 status[reason]+=1
 if reason=='candidate':verified.append(r);seen_keys.add(key)
 elif reason in ('ko_conflict','markup_mismatch'):review.append(r)
def save(name,rows):
 with gzip.open(out/name,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
save('source_anchored_supplements.jsonl.gz',verified)
save('source_anchored_review.jsonl.gz',review)
report={'prioritized_source_rows':sum(source_counts.values()),'matched_by_class':dict(source_counts),'unique_source_anchored_candidates':len(verified),'excluded_or_reviewed':len(review),'reason_counts':dict(status),'note':'Exact source ESM text/type/field corroboration, target ESM text/field and index validation. Multiple original records still require context review before patching.'}
(out/'source_anchored_supplement_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('REPORT',json.dumps(report,ensure_ascii=True),flush=True)
