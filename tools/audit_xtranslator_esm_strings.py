"""Extract translatable ESM fields using xTranslator's *installed* Fallout4 _recorddefs.txt.
Then compare against the version-pinned indexed Korean assignment plans.
Read-only. This does not prove runtime reachability or produce an ESP.

Reference source: https://github.com/MGuffin/xTranslator
  TESVT_espDefinition.pas: initrecDefList / islstringRecord / getFieldfromBuffer
MPL-2.0 reference; original source code is not copied into this script.
"""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,re,struct,zlib

ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
GAME=Path(r'C:\Games\Steam\steamapps\common\Fallout 4')
XTRANSLATOR=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/Data/Fallout4/_recorddefs.txt')
RECORD_DEF=re.compile(r'^Def_:([A-Z0-9*]{4})=([A-Z0-9*]{4})=([012])([*?!]?)(?:-(proc\d+))?$')
DISPLAY_TYPES={'INFO','DIAL','TERM','MESG','QUST','LSCR','BOOK','NOTE','NPC_','TACT',
 'WEAP','ARMO','AMMO','MISC','ALCH','INGR','CONT','DOOR','FURN','ACTI','KEYM','PERK',
 'CELL','WRLD','FACT','SPEL','MGEF','ENCH','OMOD','FLOR','RACE','REGN','AVIF','WOOP'}
DIRECT_UI={'INFO','DIAL','TERM','MESG','QUST','LSCR','BOOK','NOTE'}
def parse_defs(path):
 rules=[]
 for line in path.read_text(encoding='utf-8-sig').splitlines():
  line=line.strip()
  m=RECORD_DEF.fullmatch(line)
  if m:
   field,record,group,special,proc=m.groups()
   rules.append({'field':field,'record':record,'group':int(group),'special':special,'proc':proc})
 return rules
rules=parse_defs(XTRANSLATOR)
def is_translatable(typ,field):
 for r in rules:
  if r['field']==field and (r['record']==typ or r['record']=='****'):
   if r['special']=='?':return None
   return r
 return None
def scan_fields(buf):
 pos=0;extended=0;counter=Counter()
 while pos+6<=len(buf):
  fld,n=struct.unpack_from('<4sH',buf,pos);pos+=6
  if fld==b'XXXX':
   if n!=4 or pos+4>len(buf):break
   extended=struct.unpack_from('<I',buf,pos)[0];pos+=4;continue
  n=extended or n;extended=0
  if pos+n>len(buf):break
  field=fld.decode('ascii','replace');idx=counter[field];counter[field]+=1
  yield field,idx,buf[pos:pos+n]
  pos+=n
def readable(raw):
 if not raw or len(raw)>131072 or b'\x00' in raw[:-1]:return None
 buf=raw.rstrip(b'\0')
 if not buf:return None
 try:
  s=buf.decode('utf-8')
 except UnicodeDecodeError:
  try:s=buf.decode('cp1252')
  except UnicodeError:return None
 if not all(ch.isprintable() or ch in '\t\r\n' for ch in s):return None
 return s
def report_one(game,esm):
 folder=ROOT/'data'/game
 pin=json.loads((folder/'indexed_plan_report.json').read_text(encoding='utf-8'))['esm_sha256']
 planned={};by_src=Counter()
 for src,fn in [('existing','indexed_patch_plan_candidates.jsonl.gz'),('strict','indexed_patch_plan_v2_strict_extra.jsonl.gz')]:
  with gzip.open(folder/fn,'rt',encoding='utf-8') as f:
   for line in f:
    r=json.loads(line)
    key=(int(r['target_formid'],16),r['record_type'],r['field'],int(r['target_field_occurrence_index']))
    if key in planned and planned[key]!=(r['english'],r['korean'],src):
     raise ValueError('target assignment conflict '+str(key))
    planned[key]=(r['english'],r['korean'],src)
    by_src[src]+=1
 medium=set()
 with gzip.open(folder/'visible_reuse_context_review.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   r=json.loads(line)
   idx=r.get('field_index',r.get('target_field_occurrence_index'))
   if idx is not None:
    medium.add((int(r['target_formid'],16),r['record_type'],r['field'],int(idx),r['english']))
 stats=Counter();types=defaultdict(Counter);unknown=Counter();new_fields=Counter();examples=defaultdict(list)
 high=Counter();high_uniques=defaultdict(set)
 source=esm.stat();end=source.st_size
 out_path=folder/'xtranslator_residual_candidates.jsonl.gz'
 csv_path=folder/'xtranslator_residual_review.csv'
 with esm.open('rb') as f,gzip.open(out_path,'wt',encoding='utf-8',compresslevel=6) as out,csv_path.open('w',encoding='utf-8-sig',newline='') as cf:
  writer=csv.writer(cf)
  writer.writerow(['priority','formid','record_type','field','occurrence_index','group','english_escaped','status'])
  pos=0
  while pos<end:
   f.seek(pos);head=f.read(24)
   if len(head)!=24:raise ValueError('truncated record '+str(pos))
   tag,n,flags,fid,_,_=struct.unpack('<4sIIIII',head)
   if tag==b'GRUP':
    if n<24 or pos+n>end:raise ValueError('bad group')
    pos+=24;continue
   if n>16*1024*1024 or pos+n+24>end:raise ValueError('bad record')
   typ=tag.decode('ascii','replace')
   buf=f.read(n)
   if flags&0x00040000:
    expected=struct.unpack_from('<I',buf)[0]
    buf=zlib.decompress(buf[4:])
    if len(buf)!=expected:raise ValueError('invalid compressed data')
   for field,idx,raw in scan_fields(buf):
    definition=is_translatable(typ,field)
    if definition is None:continue
    stats['xtranslator_field_occurrences']+=1
    text=readable(raw)
    if text is None:
     stats['not_decoded_as_plain_text']+=1
     types[typ+'/'+field]['not_decoded']+=1
     continue
    stats['xtranslator_decoded_text_occurrences']+=1
    key=(fid,typ,field,idx)
    value=planned.get(key)
    if value and value[0]==text:
     status='planned_'+value[2]
    elif value:
     status='plan_english_mismatch'
    elif (fid,typ,field,idx,text) in medium:
     status='existing_korean_needs_context'
    else:
     status='missing_translation_match'
    stats[status]+=1
    types[typ+'/'+field][status]+=1
    if status=='planned_existing' or status=='planned_strict':continue
    p='P0' if typ in DIRECT_UI else 'P1' if typ in DISPLAY_TYPES else 'P2'
    if definition['proc'] is not None:
     p='P2' # conditional field in xTranslator; must check context
    if status in ('missing_translation_match','plan_english_mismatch'):
     high[p]+=1
     high_uniques[(typ,field,p)].add(text)
    if len(examples[(typ,field,status)])<3:
     examples[(typ,field,status)].append({'id':f'{fid:08X}','english':text[:180]})
    row={'formid':f'{fid:08X}','record_type':typ,'field':field,'index':idx,'group':definition['group'],'special':definition['special'],'conditional_proc':definition['proc'],'english':text,'status':status,'priority':p}
    out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
    # single physical CSV row per record: no multiline source spillover, preserve escapes
    writer.writerow([p,row['formid'],typ,field,idx,definition['group'],json.dumps(text,ensure_ascii=False),status])
   pos+=24+n
 # Inputs version-pin
 h=hashlib.sha256()
 with esm.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 if esm.stat().st_size!=source.st_size or esm.stat().st_mtime_ns!=source.st_mtime_ns or h.hexdigest()!=pin:
  raise RuntimeError('ESM changed or differs from report: stop')
 # New record types and fields our earlier manual scanner did not cover
 previous={
 'INFO':{'RNAM','NAM1'},'DIAL':{'FULL'},'TERM':{'FULL','ITXT','BTXT','UNAM'},
 'NOTE':{'FULL','TNAM','DESC'},'MESG':{'FULL','DESC','ITXT','DNAM'},
 'QUST':{'FULL','CNAM'},'LSCR':{'DESC'},'BOOK':{'FULL','DESC','CNAM'},
 'NPC_':{'FULL'},'ARMO':{'FULL','DESC'},'WEAP':{'FULL','DESC'},
 'AMMO':{'FULL'},'MISC':{'FULL','DESC'},'ALCH':{'FULL','DESC'},
 'INGR':{'FULL'},'CONT':{'FULL'},'KEYM':{'FULL'},'ACTI':{'FULL'},
 'DOOR':{'FULL'},'FURN':{'FULL'},'CELL':{'FULL'},'WRLD':{'FULL'},
 'PERK':{'FULL','DESC'},'SPEL':{'FULL','DESC'},'MGEF':{'FULL','DNAM'},
 'FACT':{'FULL'},'EXPL':{'FULL'},'OMOD':{'FULL','DESC'},'TACT':{'FULL'},
 }
 for signature,counts in types.items():
  typ,field=signature.split('/')
  if field not in previous.get(typ,set()):
   new_fields[signature]=sum(counts.values())
 summary={
  'game':game,'definitions_path':str(XTRANSLATOR),'definitions_sha256':hashlib.sha256(XTRANSLATOR.read_bytes()).hexdigest(),
  'definition_rule_count':len(rules),'esm_sha256':pin,'source_size':source.st_size,
  'counts':dict(stats),'by_record_field':{k:dict(v) for k,v in sorted(types.items())},
  'new_fields_not_in_old_handmade_scanner':dict(new_fields.most_common()),
  'unmatched_occurrences_by_priority':dict(high),
  'missing_distinct_text_by_field_and_priority':[{'type':tp,'field':field,'priority':p,'distinct_english':len(v)} for (tp,field,p),v in sorted(high_uniques.items(),key=lambda x:-len(x[1]))],
  'samples':{'/'.join([a,b,c]):v for (a,b,c),v in examples.items()},
  'limitations':'Uses installed xTranslator _recorddefs field definitions and mirrors plain string fallback, but not all conditional proc logic, dynamic VMAD/script strings, BSA/BA2, or in-game reachability. A field can be translatable yet unused in game. No original ESM was modified.'
 }
 (folder/'xtranslator_extraction_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('GAME',game,'RULES',len(rules),'COUNTS',dict(stats),'PRIORITY',dict(high),flush=True)
 print('NEW_FIELDS',new_fields.most_common(20),'TOP_UNTRANSLATED',summary['missing_distinct_text_by_field_and_priority'][:15],flush=True)
for game in ('fo3','fnv'):
 esm=GAME/'Data'/('Fallout34.esm' if game=='fo3' else 'FalloutNV34.esm')
 if not esm.is_file() and game=='fnv':esm=GAME/'Fallout34_Work'/'fnv'/'staging'/'Data'/'FalloutNV34.esm'
 report_one(game,esm)
