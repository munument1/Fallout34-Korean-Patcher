"""Persist converter v0.9.33 FormID map and selected generated origin keys before installer cleans its working files."""
from pathlib import Path
import gzip,hashlib,json
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
folder=root/'data'/'fnv'
source=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv\work\reports')
src_map=source/'formid_map.tsv'
src_keys=source/'formid_keys.tsv'
dest_map=folder/'converter_formid_map.tsv.gz'
dest_keys=folder/'converter_origin_keys_selected.tsv.gz'
if dest_map.exists() or dest_keys.exists():raise RuntimeError('Existing converter snapshot; refusing to overwrite')
wanted=set()
for line in gzip.open(folder/'unlinked_field_entries.jsonl.gz','rt',encoding='utf-8'):
 try:
  s=line.partition('"target_formid":"')[2][:8]
  if len(s)==8:wanted.add(s)
 except Exception:pass
print('TARGET IDS TO SAVE',len(wanted),flush=True)
h_map=hashlib.sha256();map_lines=0
with src_map.open('rb') as f, dest_map.open('wb') as raw:
 with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=6,mtime=0) as gz:
  for line in f:
   h_map.update(line);gz.write(line);map_lines+=1
print('MAP STORED',map_lines,dest_map.stat().st_size,flush=True)
h_keys=hashlib.sha256();all_count=0;selected=0
with src_keys.open('rb') as f,dest_keys.open('wb') as raw:
 with gzip.GzipFile(filename='',mode='wb',fileobj=raw,compresslevel=6,mtime=0) as gz:
  head=f.readline();h_keys.update(head);gz.write(head)
  for line in f:
   h_keys.update(line);all_count+=1
   fid=line[:8].decode('ascii','replace')
   if fid in wanted:
    gz.write(line);selected+=1
report={'source_formid_map':str(src_map),'source_formid_keys':str(src_keys),'full_map_rows':map_lines-1,'full_keys_rows':all_count,'selected_key_rows':selected,'unlinked_target_ids':len(wanted),'source_map_sha256':h_map.hexdigest(),'source_keys_sha256':h_keys.hexdigest(),'compressed_map_bytes':dest_map.stat().st_size,'compressed_selected_keys_bytes':dest_keys.stat().st_size,'output_map':str(dest_map),'output_selected_keys':str(dest_keys),'note':'All map rows retained; generated keys only for currently unlinked target IDs. Other keys can be regenerated from converter. No original ESM/ESP data is included.'}
(folder/'converter_snapshot_manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('SNAPSHOT',json.dumps({k:v for k,v in report.items() if k not in ('source_formid_map','source_formid_keys','output_map','output_selected_keys','note')},ensure_ascii=True),flush=True)
