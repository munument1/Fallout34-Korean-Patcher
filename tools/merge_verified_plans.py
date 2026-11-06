from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,hashlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
folder=root/'data'/'fo3'
esm=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm')
old=json.loads((folder/'verified_plan_report.json').read_text(encoding='utf-8'))
h=hashlib.sha256()
with esm.open('rb') as f:
 for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
assert h.hexdigest()==old['esm_sha256'], 'ESM changed, regenerate all plans'
sources={
 'formid_map_tsv':'verified_assignments.jsonl.gz',
 'direct_fo3_id_esm_match':'direct_formid_exact.jsonl.gz',
 'dlc_modal_offset_esm_match':'dlc_direct_exact.jsonl.gz'
}
by_key=defaultdict(list);count=Counter();perplugin=Counter()
for origin,name in sources.items():
 with gzip.open(folder/name,'rt',encoding='utf-8') as f:
  for line in f:
   r=json.loads(line)
   r['mapping_method']=origin
   key=(r['target_formid'].upper(),r['record_type'],r['field'],r['english'])
   by_key[key].append(r)
   count[origin]+=1
   perplugin[(origin,r['source_plugin'])]+=1
final=[];review=[]
conflicts=0;duplicates=0;duplicate_source=0
for key,items in by_key.items():
 translations={r['korean'] for r in items}
 source_keys={r['source_key'] for r in items}
 if len(translations)>1 or len(source_keys)>1:
  conflicts+=1
  for r in items:
   r['qa_reason']='conflicting_translation_or_origin'
   review.append(r)
 else:
  r=dict(items[0])
  if len(items)>1:
   duplicates+=len(items)-1
   r['evidence_count']=len(items)
   r['sst_indices']=sorted(set(str(x['sub_index'])+':'+str(x['sub_index_max']) for x in items))
  final.append(r)
final.sort(key=lambda r:(r['target_formid'],r['record_type'],r['field'],r['english']))
out=folder/'verified_assignments_all.jsonl.gz'
with gzip.open(out,'wt',encoding='utf-8',compresslevel=6) as f:
 for r in final:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
with gzip.open(folder/'mapping_conflicts.jsonl.gz','wt',encoding='utf-8',compresslevel=6) as f:
 for r in review:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
summary={
 'status':'candidate translation memory only; no ESP/STRINGS installed or produced',
 'source_esm_sha256':h.hexdigest(),
 'source_esm_size':esm.stat().st_size,
 'original_formid_map_rows':321102,
 'previous_unique_verified':old['unique_safe_assignments'],
 'method_rows':dict(count),
 'method_per_plugin':{f'{a}|{b}':n for (a,b),n in sorted(perplugin.items())},
 'new_unique_verified_assignments':len(final),
 'recovered_vs_previous':len(final)-old['unique_safe_assignments'],
 'deduplicated_rows':duplicates,
 'conflict_keys_excluded':conflicts,
 'conflict_rows_review':len(review),
 'review_remains_from_first_round':old['review_rows'],
 'unmatched_direct_fo3':json.loads((folder/'direct_formid_probe.json').read_text(encoding='utf-8'))['results'],
 'dlc_unmapped_direct':json.loads((folder/'dlc_direct_probe.json').read_text(encoding='utf-8'))['results'],
 'warnings':[
 'All assignments are version-specific and matched by FO4 ESM record type, field and exact English.',
 'Repeated field occurrences and FO4 runtime rendering have not yet been tested.',
 'Any xEdit/ESP writer must respect correct INFO response index, master IDs, compressed records, localized variants and load order.',
 'No installed mod file was changed. Source SST files were read only.'
 ]
}
(folder/'combined_plan_report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('COUNT',json.dumps({k:v for k,v in summary.items() if k not in ('method_per_plugin','warnings')},ensure_ascii=True),flush=True)
print('OUTPUT',out, 'SIZE',out.stat().st_size)
