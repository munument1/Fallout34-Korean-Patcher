from pathlib import Path
from collections import Counter,defaultdict
import json,gzip
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
data=root/'data'/'fo3'
groups=[('direct_mapping_review','review_needed.jsonl.gz'),('fo3_direct_review','direct_formid_review.jsonl.gz'),('dlc_direct_review','dlc_direct_review.jsonl.gz')]
total=Counter()
out={}
for name,file in groups:
 reasons=Counter();types=Counter();fields=Counter();plugins=Counter();sample=defaultdict(list);unique=set()
 with gzip.open(data/file,'rt',encoding='utf-8') as f:
  for line in f:
   r=json.loads(line)
   reason=r.get('qa_reason',r.get('qa_status','none'))
   reasons[reason]+=1;types[r['record_type']]+=1;fields[(r['record_type'],r['field'])]+=1;plugins[r['source_plugin']]+=1
   unique.add((r['source_key'],r['record_type'],r['field'],r['english'],r['korean']))
   if len(sample[reason])<7:sample[reason].append({'source':r['source_key'],'type':r['record_type'],'field':r['field'],'english':r['english'][:100],'korean':r['korean'][:100]})
 total.update(reasons)
 out[name]={'count':sum(reasons.values()),'unique_translation_items':len(unique),'reasons':dict(reasons),'types':types.most_common(25),'fields':[((k[0],k[1]),v) for k,v in fields.most_common(20)],'plugins':dict(plugins),'samples':dict(sample)}
print('TOTAL',dict(total),'SUM',sum(total.values()))
for name,value in out.items():
 print('GROUP',name,'UNIQUE',value['unique_translation_items'],'REASONS',value['reasons'],'TYPES',value['types'][:11],'FIELDS',value['fields'][:12])
print('EXAMPLES',json.dumps({n:v['samples'] for n,v in out.items()},ensure_ascii=True)[:2500])
(data/'outstanding_translation_audit.json').write_text(json.dumps({'total':dict(total),'overall_review_rows':sum(total.values()),'groups':out},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
