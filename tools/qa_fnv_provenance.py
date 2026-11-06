"""Validate source-anchored Korean assignments for duplicate target occurrence and markup safety."""
from collections import defaultdict,Counter
from pathlib import Path
import gzip,json,re
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\data\fnv')
src=root/'provenance_text_candidates.jsonl.gz'
# xTranslator preserved placeholders and dynamic markup need exact preservation.
pattern=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}')
rows=[];seen=defaultdict(set);duplicate=Counter();questionable=Counter()
for line in gzip.open(src,'rt',encoding='utf-8'):
 r=json.loads(line)
 k=(r['target_formid'],r['record_type'],r['field'],r['target_field_occurrence_index'])
 seen[k].add((r['english'],r['korean']))
 rows.append((k,r))
conflicts={k for k,v in seen.items() if len(v)>1}
safe=[];review=[];samples=[]
for k,r in rows:
 if k in conflicts:reason='target_occurrence_conflicting_translations'
 elif Counter(pattern.findall(r['english']))!=Counter(pattern.findall(r['korean'])):reason='placeholder_mismatch'
 elif not r['korean'] or r['korean']==r['english']:reason='not_translated'
 else:reason='pass'
 questionable[reason]+=1
 if reason=='pass':safe.append(r)
 else:
  r['qa_reason']=reason;review.append(r)
  if len(samples)<12:samples.append({'formid':r['target_formid'],'type':r['record_type'],'field':r['field'],'en':r['english'][:120],'ko':r['korean'][:120],'reason':reason})
def save(name,arr):
 with gzip.open(root/name,'wt',encoding='utf-8',compresslevel=6) as f:
  for row in arr:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
save('provenance_qa_pass.jsonl.gz',safe)
save('provenance_qa_review.jsonl.gz',review)
report={'original_candidates':len(rows),'qa_pass':len(safe),'needs_review':len(review),'target_occurrence_conflict_keys':len(conflicts),'qa_classes':dict(questionable),'examples':samples,'note':'Only source IDs and English/KO exact match and placeholder validation; not actual game runtime evaluation.'}
(root/'provenance_qa_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('RESULT',json.dumps({k:v for k,v in report.items() if k not in ('examples','note')},ensure_ascii=True),flush=True)
print('EXAMPLES',json.dumps(samples[:4],ensure_ascii=True))
