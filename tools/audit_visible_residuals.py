"""Identify unresolved visible-field candidates after CURRENT indexed patch plans; distinct from general developer/internal text."""
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,re,struct,zlib,hashlib
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
FO4=Path(r'C:\Games\Steam\steamapps\common\Fallout 4')
TARGETS={'fo3':FO4/'Data'/'Fallout34.esm','fnv':FO4/'Fallout34_Work'/'fnv'/'staging'/'Data'/'FalloutNV34.esm'}
FIELDS={
 'INFO':{'RNAM':'dialogue_choice','NAM1':'dialogue_subtitle'},
 'DIAL':{'FULL':'dialogue_topic_title'},
 'TERM':{'FULL':'terminal_title','ITXT':'terminal_option','BTXT':'terminal_option','UNAM':'terminal_body'},
 'NOTE':{'FULL':'note_title','TNAM':'note_body','DESC':'note_body'},
 'MESG':{'FULL':'message_title','DESC':'message_body','ITXT':'message_option','DNAM':'message_body'},
 'QUST':{'FULL':'quest_title','CNAM':'quest_stage'},
 'LSCR':{'DESC':'loading_screen_tip'},
 'NPC_':{'FULL':'npc_name'},
 'TACT':{'FULL':'creature_name'},
 'ARMO':{'FULL':'armor_name','DESC':'armor_description'},
 'WEAP':{'FULL':'weapon_name','DESC':'weapon_description'},
 'AMMO':{'FULL':'ammo_name'},
 'MISC':{'FULL':'item_name','DESC':'item_description'},
 'ALCH':{'FULL':'consumable_name','DESC':'consumable_description'},
 'INGR':{'FULL':'ingredient_name'},
 'BOOK':{'FULL':'book_title','DESC':'book_text','CNAM':'book_text'},
 'CONT':{'FULL':'container_name'},
 'KEYM':{'FULL':'key_name'},
 'ACTI':{'FULL':'activator_name'},
 'DOOR':{'FULL':'door_name'},
 'FURN':{'FULL':'furniture_name'},
 'CELL':{'FULL':'cell_name'},
 'WRLD':{'FULL':'world_name'},
 'PERK':{'FULL':'perk_name','DESC':'perk_description'},
 'SPEL':{'FULL':'spell_name','DESC':'spell_description'},
 'MGEF':{'FULL':'effect_name','DNAM':'effect_description'},
 'FACT':{'FULL':'faction_name'},
 'EXPL':{'FULL':'explosion_name'},
 'OMOD':{'FULL':'mod_name','DESC':'mod_description'},
}
# Special marker prefix not an absolute exclusion: just a triage hint.
INTERNAL_RE=re.compile(r'^(?:[a-zA-Z]+\d*[A-Z][A-Za-z0-9_]+|F34_|DLC\d+|MQ\d+|[A-Za-z]+_[A-Za-z\d_]+)$')
def chunks(blob):
 pos=0;extended=0;counter=Counter()
 while pos+6<=len(blob):
  typ,n=struct.unpack_from('<4sH',blob,pos);pos+=6
  if typ==b'XXXX':
   if n!=4 or pos+4>len(blob):break
   extended=struct.unpack_from('<I',blob,pos)[0];pos+=4;continue
  n=extended or n;extended=0
  if pos+n>len(blob):break
  kind=typ.decode('ascii','replace');counter[kind]+=1
  yield kind,counter[kind]-1,blob[pos:pos+n]
  pos+=n
def decode(b):
 if len(b)<2 or len(b)>131072 or b'\x00' in b[:-1]:return None
 b=b.rstrip(b'\0')
 for encoding in ('utf-8','cp1252'):
  try:
   text=b.decode(encoding)
   if all(ch.isprintable() or ch in '\r\n\t' for ch in text):return text
  except UnicodeError:pass
 return None
for game,esm in TARGETS.items():
 if not esm.exists() and game=='fnv':esm=FO4/'Data'/'FalloutNV34.esm'
 if not esm.exists():print('MISSING_SOURCE_ESM',game);continue
 folder=ROOT/'data'/game
 assignments=defaultdict(set)
 for line in gzip.open(folder/'indexed_patch_plan_candidates.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line)
  assignments[(int(r['target_formid'],16),r['record_type'],r['field'],int(r['target_field_occurrence_index']))].add(r['english'])
 total=Counter();covered=Counter();residual=Counter();uniq=defaultdict(set);samples=defaultdict(list);internal=Counter()
 path=folder/'visible_residual_candidates.jsonl.gz'
 with esm.open('rb') as f,gzip.open(path,'wt',encoding='utf-8',compresslevel=6) as out:
  pos=0;end=esm.stat().st_size
  while pos<end:
   f.seek(pos);hdr=f.read(24)
   if len(hdr)!=24:raise ValueError('truncated record')
   typ,size,flags,fid,_,_=struct.unpack('<4sIIIII',hdr)
   if typ==b'GRUP':pos+=24;continue
   if size>16*1024*1024 or pos+24+size>end:raise ValueError('record size invalid')
   kind=typ.decode('ascii','replace')
   if kind in FIELDS:
    raw=f.read(size)
    if flags&0x00040000:
     if len(raw)<4:raise ValueError('compressed record short')
     expected=struct.unpack_from('<I',raw)[0]
     raw=zlib.decompress(raw[4:])
     if expected!=len(raw):raise ValueError('zlib size')
    for tag,index,buf in chunks(raw):
     label=FIELDS[kind].get(tag)
     if label is None:continue
     eng=decode(buf)
     if not eng or not re.search('[A-Za-z]{2}',eng) or len(eng.strip())<3:continue
     cat=kind+'/'+tag
     total[cat]+=1
     if eng in assignments.get((fid,kind,tag,index),set()):
      covered[cat]+=1;continue
     residual[cat]+=1;uniq[cat].add(eng)
     is_internal=bool(INTERNAL_RE.match(eng.strip()))
     if is_internal:internal[cat]+=1
     row={'target_formid':f'{fid:08X}','record_type':kind,'field':tag,'field_index':index,'screen_category':label,'english':eng,'internal_like':is_internal}
     out.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
     if len(samples[cat])<5:samples[cat].append({'id':row['target_formid'],'text':eng[:140]})
   pos+=24+size
 report={
  'esm_path':str(esm),'scope':'known user-visible candidate fields, not complete runtime reachability',
  'total_visible_field_string_occurrences':sum(total.values()),
  'covered_by_indexed_plan_occurrences':sum(covered.values()),
  'residual_visible_field_occurrences':sum(residual.values()),
  'residual_unique_english_sum_by_field':sum(map(len,uniq.values())),
  'internal_like_occurrences':sum(internal.values()),
  'by_field':[{'field':k,'total':total[k],'covered':covered[k],'residual':n,'distinct_english':len(uniq[k]),'internal_like':internal[k],'samples':samples[k]} for k,n in residual.most_common()],
  'warning':'Visible-field only not confirmed runtime usage. Not yet an ESP. Duplicate generated dialogue can multiply occurrences.'
 }
 (folder/'visible_residual_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('GAME',game,'SUMMARY',json.dumps({k:v for k,v in report.items() if k not in ('by_field','warning','scope','esm_path')},ensure_ascii=True),flush=True)
 for r in report['by_field'][:20]:print('FIELD',r['field'],'TOTAL',r['total'],'COVERED',r['covered'],'RESID',r['residual'],'UNIQUE',r['distinct_english'],'INTERNAL',r['internal_like'],'SAMPLE',r['samples'][:2],flush=True)
