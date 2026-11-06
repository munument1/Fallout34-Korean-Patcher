from pathlib import Path
from collections import Counter
import json,hashlib,shutil
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
base=Path(r'C:\Games\Steam\steamapps\common\Fallout 4')
new=base/'Fallout34_Work'/'fnv'/'staging'/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
installed=base/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
if not new.exists():new=installed
old=root/'work'/'fo3'/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
dict_file=root/'data'/'mcm'/'translations_ko.json'
dictionary=json.loads(dict_file.read_text(encoding='utf-8-sig'))
orig=json.loads(new.read_text(encoding='utf-8-sig'))
orig_inst=json.loads(installed.read_text(encoding='utf-8-sig'))
if orig!=orig_inst:raise RuntimeError('Current Fallout 4 MCM differs from FNV staging MCM. Manual review required')
out=json.loads(new.read_text(encoding='utf-8-sig'))
counts=Counter()
def walk(node):
 if isinstance(node,dict):
  for k,v in node.items():
   if k in ('displayName','pageDisplayName','text','help') and isinstance(v,str):
    if v in dictionary:
     node[k]=dictionary[v];counts['ui_fields']+=1
    elif v=='Fallout 34':counts['brand_not_changed']+=1
    else:raise ValueError('Unmapped UI field: '+v)
   elif k=='options' and isinstance(v,list):
    for i,opt in enumerate(v):
     if opt not in dictionary:raise ValueError('Unmapped option: '+str(opt))
     v[i]=dictionary[opt];counts['ui_fields']+=1
   else:walk(v)
 elif isinstance(node,list):
  for v in node:walk(v)
walk(out)
old_ko=json.loads(old.read_text(encoding='utf-8'))
if out!=old_ko:raise ValueError('New MCM translated output differs from previous FO3 draft')
dst=root/'work'/'common'/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
dst.parent.mkdir(parents=True,exist_ok=True);dst.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result={'source_fnv_mcm':str(new),'source_installed_mcm':str(installed),'source_json_matches':True,'fo3_korean_equals_fnv_korean':True,'ui_translated':counts['ui_fields'],'output':str(dst),'output_sha256':sha(dst),'status':'Ready as optional MCM file; not installed into game'}
(root/'data'/'mcm'/'shared_mcm_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('REPORT',json.dumps(result,ensure_ascii=True))
