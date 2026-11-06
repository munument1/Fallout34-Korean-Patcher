from __future__ import annotations
from pathlib import Path
from collections import defaultdict, Counter
import gzip,json,csv,re,struct
work=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
source=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\work\reports\formid_map.tsv')
out=work/'data'/'fo3'/'missing_mapping_audit.json'
by_source=defaultdict(list);deltas=defaultdict(Counter);n=0
with source.open('r',encoding='utf-8') as f:
 for r in csv.DictReader(f,delimiter='\t'):
  n+=1
  key=r['source'].casefold();by_source[key].append((r['formid'],r['type']))
  try:
   plugin,local=key.split(':',1)
   deltas[plugin][int(r['formid'],16)-int(local,16)]+=1
  except:pass
unmatched=work/'data'/'fo3'/'unmatched_sst.jsonl.gz'
utypes=Counter();uplug=Counter();reason=Counter();samples=defaultdict(list); direct_other_type=0
with gzip.open(unmatched,'rt',encoding='utf-8') as f:
 for line in f:
  row=json.loads(line)
  utypes[row['record_type']]+=1;uplug[row['source_plugin']]+=1
  key=row['source_key']
  if key in by_source:
   reason['source_present_type_changed']+=1
   if len(samples['source_present_type_changed'])<8:samples['source_present_type_changed'].append({'sst_source':key,'sst_type':row['record_type'],'map':by_source[key][:5]})
  else:
   reason['source_not_in_map']+=1
   if len(samples['source_not_in_map'])<8:samples['source_not_in_map'].append({'sst_source':key,'type':row['record_type'],'field':row['field'],'eng':row['english'][:85]})
data={'map_rows':n,'unique_source_keys':len(by_source),'unmapped_types':utypes.most_common(35),'unmapped_plugins':uplug.most_common(),'reasons':reason,'deltas':{a:c.most_common(8) for a,c in deltas.items()},'samples':samples}
out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('MAP',n,'KEYS',len(by_source))
print('UNMATCHED TYPES',utypes.most_common(18))
print('UNMATCHED PLUGINS',uplug.most_common())
print('REASONS',reason)
print('DELTAS',json.dumps(data['deltas'],ensure_ascii=False))
print('SAMPLES',json.dumps(samples,ensure_ascii=True)[:1500])
