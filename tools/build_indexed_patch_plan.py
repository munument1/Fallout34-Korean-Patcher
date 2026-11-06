"""Build VERSION-LOCKED, occurrence-indexed FO4 text translation plan. NEVER edits ESM or installs anything."""
from pathlib import Path
from collections import defaultdict,Counter
import argparse,gzip,json,hashlib,struct,zlib,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
PATTERN=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}')
def fields(b):
 pos=0;ext=0;index=Counter()
 while pos+6<=len(b):
  typ,n=struct.unpack_from('<4sH',b,pos);pos+=6
  if typ==b'XXXX':
   if n!=4 or pos+4>len(b):break
   ext=struct.unpack_from('<I',b,pos)[0];pos+=4;continue
  n=ext or n;ext=0
  if pos+n>len(b):break
  t=typ.decode('ascii','replace')
  index[t]+=1
  yield t,index[t]-1,b[pos:pos+n]
  pos+=n
def decode(b):
 if not b or len(b)>131072 or b'\0' in b[:-1]:return None
 b=b.rstrip(b'\0')
 for codec in ('utf-8','cp1252'):
  try:
   s=b.decode(codec)
   if all(ch.isprintable() or ch in '\r\n\t' for ch in s):return s
  except UnicodeError:pass
 return None
def write(path,rows):
 with gzip.open(path,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
def run(game):
 folder=root/'data'/game
 if game=='fo3':
  esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm')
  initial='verified_assignments_all.jsonl.gz'
  supplement=['migrated_verified_candidates.jsonl.gz','source_anchored_supplements.jsonl.gz']
  expected=json.loads((folder/'combined_plan_report.json').read_text(encoding='utf-8'))['source_esm_sha256']
 else:
  esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv\staging\Data\FalloutNV34.esm')
  if not esm.exists():esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Data\FalloutNV34.esm')
  initial='exact_assignments.jsonl.gz'
  supplement=['migrated_verified_candidates.jsonl.gz','provenance_qa_pass.jsonl.gz']
  expected=json.loads((folder/'verification_report.json').read_text(encoding='utf-8'))['esm_sha256']
 staged=defaultdict(list);item_counts=Counter()
 with gzip.open(folder/initial,'rt',encoding='utf-8') as f:
  for line in f:
   r=json.loads(line);r['plan_source']='direct_sst_formid_english_match'
   staged[int(r['target_formid'],16)].append(r);item_counts[r['plan_source']]+=1
 print(game,'DIRECT ENTRY COUNT',sum(map(len,staged.values())),flush=True)
 resolved=[];rejected=[];issues=Counter();source_types=Counter()
 start=esm.stat()
 with esm.open('rb') as f:
  pos=0;end=start.st_size
  while pos<end:
   f.seek(pos);head=f.read(24)
   if len(head)!=24:raise ValueError('bad header')
   typ,n,flags,fid,_,_=struct.unpack('<4sIIIII',head)
   if typ==b'GRUP':pos+=24;continue
   if pos+24+n>end or n>16*1024*1024:raise ValueError('invalid record')
   if fid in staged:
    raw=f.read(n)
    if flags&0x00040000:
     length=struct.unpack_from('<I',raw)[0]
     raw=zlib.decompress(raw[4:])
     if len(raw)!=length:raise ValueError('bad compressed data')
    strings=defaultdict(list)
    for t,idx,b in fields(raw):
     eng=decode(b)
     if eng is not None:strings[t].append((idx,eng))
    rec_type=typ.decode('ascii','replace')
    for r in staged.pop(fid):
     match=[idx for idx,s in strings[r['field']] if s==r['english']]
     if rec_type!=r['record_type']:reason='record_type_changed_during_plan'
     elif not match:reason='text_not_found'
     elif len(match)>1:reason='ambiguous_repeated_english'
     else:reason=None
     if reason:
      item=dict(r);item['qa_reason']=reason;rejected.append(item);issues[reason]+=1
     else:
      item=dict(r);item['target_field_occurrence_index']=match[0]
      resolved.append(item)
   pos+=24+n
 for remaining in staged.values():
  for r in remaining:
   item=dict(r);item['qa_reason']='target_id_not_found'
   rejected.append(item);issues['target_id_not_found']+=1
 print(game,'DIRECT OCCURRENCE INDEXED',len(resolved),'DIRECT REVIEW',len(rejected),issues,flush=True)
 for s in supplement:
  with gzip.open(folder/s,'rt',encoding='utf-8') as f:
   for line in f:
    r=json.loads(line)
    item=dict(r)
    item['plan_source']=s.replace('.jsonl.gz','')
    if 'target_field_occurrence_index' not in item:raise ValueError('Missing target field index in '+s)
    resolved.append(item);item_counts[item['plan_source']]+=1
 # All targeted assignment keys must agree on English and Korean.
 by_target=defaultdict(list)
 for r in resolved:
  key=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'])
  by_target[key].append(r)
 conflicts=[];unique=[];qa=Counter()
 for key,rows in by_target.items():
  pair={(r['english'],r['korean']) for r in rows}
  if len(pair)>1:
   qa['same_target_occurrence_conflict']+=len(rows)
   for r in rows:
    item=dict(r);item['qa_reason']='same_target_occurrence_conflict';conflicts.append(item)
   continue
  r=next(iter(rows))
  if not r['korean'] or r['korean']==r['english']:reason='untranslated'
  elif Counter(PATTERN.findall(r['english']))!=Counter(PATTERN.findall(r['korean'])):reason='placeholder_mismatch'
  else:reason=None
  if reason:
   qa[reason]+=1
   item=dict(r);item['qa_reason']=reason;conflicts.append(item)
  else:unique.append(r);qa['qa_pass_unique']+=1
 # Version pin. Input may be staging during active conversion.
 h=hashlib.sha256()
 with esm.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 if start.st_size!=esm.stat().st_size or start.st_mtime_ns!=esm.stat().st_mtime_ns:raise RuntimeError('ESM modified during plan')
 if h.hexdigest()!=expected:raise RuntimeError('ESM hash mismatches previous verification. Recheck!')
 unique.sort(key=lambda r:(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index']))
 write(folder/'indexed_patch_plan_candidates.jsonl.gz',unique)
 write(folder/'indexed_plan_review.jsonl.gz',rejected+conflicts)
 report={'game':game,'esm_sha256':expected,'esm_path':str(esm),'input_direct_rows':item_counts['direct_sst_formid_english_match'],'supplement_rows':{k:v for k,v in item_counts.items() if k!='direct_sst_formid_english_match'},'direct_occurence_indexed':len(resolved)-sum(v for k,v in item_counts.items() if k!='direct_sst_formid_english_match'),'direct_index_issue_counts':dict(issues),'target_occurrence_conflict_keys':sum(1 for rows in by_target.values() if len({(r['english'],r['korean']) for r in rows})>1),'qa_summary':dict(qa),'indexed_unique_candidate_rows':len(unique),'review_rows':len(rejected)+len(conflicts),'status':'DEVELOPMENT CANDIDATES ONLY; not a generated ESP or a tested FO4 patch','warning':'Exact ESM record/text/index proof, provenance and placeholders are checked; runtime story context, scripts and other field types still require validation. No original game files were modified.'}
 (folder/'indexed_plan_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('PLAN',game,json.dumps({k:v for k,v in report.items() if k not in ('esm_path','warning')},ensure_ascii=True),flush=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('game',choices=('fo3','fnv'));args=parser.parse_args();run(args.game)
