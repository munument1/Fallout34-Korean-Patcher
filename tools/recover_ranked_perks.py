"""Versioned name-rank synthesis for New Vegas converted PERK/FULL visible fields."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,re,importlib.util
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
spec=importlib.util.spec_from_file_location('sst',root/'tools'/'read_xtranslator_sst.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
source=defaultdict(set)
for name in ('falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal'):
 s=m.parse_sst(folder/(name+'_en_ko.sst'))
 for r in s['records']:
  if r['record_name']=='PERK' and r['field_name']=='FULL' and r['korean'] and r['korean']!=r['source']:
   source[r['source']].add(r['korean'])
folder=root/'data'/'fnv'
data=[];sums=Counter()
for line in gzip.open(folder/'visible_manual_review.jsonl.gz','rt',encoding='utf-8'):
 r=json.loads(line)
 if r['record_type']!='PERK' or r['field']!='FULL' or r['translation_status']!='no_translation_in_current_sst':continue
 match=re.fullmatch(r'(.+?) \((\d+)\)',r['english'])
 if not match:continue
 base,level=match.groups()
 if len(source[base])!=1:sums['ambiguous_or_missing']+=1;continue
 r['korean']=next(iter(source[base]))+f' ({level})'
 r['match_class']='derived_rank_suffix_from_unique_PERK_FULL_source'
 data.append(r);sums['source_unique_rank_matched']+=1
with gzip.open(folder/'ranked_perk_source_verified.jsonl.gz','wt',encoding='utf-8',compresslevel=6) as f:
 for r in data:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
(folder/'ranked_perk_report.json').write_text(json.dumps({'status':'not installed','counts':dict(sums)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',dict(sums),'SAMPLES',[(x['target_formid'],x['english'],x['korean']) for x in data[:4]])
