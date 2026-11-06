from pathlib import Path
import gzip,json,collections,importlib.util,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
spec=importlib.util.spec_from_file_location('sst',root/'tools'/'read_xtranslator_sst.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
src_folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
for game,files in [('fo3',['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta']),
                   ('fnv',['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad'])]:
 by_id=collections.defaultdict(list);by_full=collections.defaultdict(list)
 for name in files:
  parsed=mod.parse_sst(src_folder/(name+'_en_ko.sst'))
  masters=[m.lower() for m in parsed['master_files']]
  for row in parsed['records']:
   idnum=int(row['form_id'],16)
   if idnum>>24>=len(masters):continue
   key=(masters[idnum>>24],idnum&0xffffff)
   by_id[key].append((row['record_name'],row['field_name'],row['source'][:110],row['korean'][:110]))
   by_full[(row['record_name'],row['field_name'],row['source'])].append(row['korean'])
 d=root/'data'/game
 for typ,field in [('INFO','NAM1'),('INFO','RNAM'),('MESG','DESC'),('TERM','ITXT')]:
  cnt=collections.Counter();ids=collections.defaultdict(list)
  for line in gzip.open(d/'visible_manual_review.jsonl.gz','rt',encoding='utf-8'):
   r=json.loads(line)
   if r['record_type']==typ and r['field']==field and r['translation_status']=='no_translation_in_current_sst':
    cnt[r['english']]+=1
    if len(ids[r['english']])<2:ids[r['english']].append(r['target_formid'])
  print('\nGAME',game,typ,field,'TOTAL',sum(cnt.values()),'UNIQUE',len(cnt),flush=True)
  for en,n in cnt.most_common(14):
   matches=[]
   for id in ids[en]:
    low=int(id,16)&0xffffff
    key=('fallout3.esm' if game=='fo3' else 'falloutnv.esm',low)
    matches.append({'target':id,'sst_same_id':by_id[key][:4]})
   print(' ROW',n,'EN',json.dumps(en[:110],ensure_ascii=True),'EX',json.dumps(matches,ensure_ascii=True)[:800],flush=True)
