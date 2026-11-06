from pathlib import Path
import json,hashlib
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
source=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\MCM\Config\Fallout34\config.json')
dictionary=root/'data'/'mcm'/'translations_ko.json'
destination=root/'work'/'fo3'/'Data'/'MCM'/'Config'/'Fallout34'/'config.json'
src=json.loads(source.read_text(encoding='utf-8-sig'))
dst=json.loads(source.read_text(encoding='utf-8-sig'))
trans=json.loads(dictionary.read_text(encoding='utf-8-sig'))
counts={'translated_fields':0,'unchanged_brand':0,'missing':[]}
def transform(obj):
 if isinstance(obj,dict):
  for key,val in obj.items():
   if key in ('displayName','pageDisplayName','text','help') and isinstance(val,str):
    if val in trans:
     obj[key]=trans[val];counts['translated_fields']+=1
    elif val=='Fallout 34':counts['unchanged_brand']+=1
    else:counts['missing'].append([key,val])
   elif key=='options' and isinstance(val,list):
    for i,opt in enumerate(val):
     if opt not in trans: counts['missing'].append(['options',opt])
     else:obj[key][i]=trans[opt];counts['translated_fields']+=1
   else:transform(val)
 elif isinstance(obj,list):
  for entry in obj:transform(entry)
transform(dst)
if counts['missing']:raise RuntimeError('Untranslated MCM text: '+repr(counts['missing']))
def non_ui(obj):
 if isinstance(obj,dict):
  return {k:non_ui(v) for k,v in obj.items() if k not in ('displayName','pageDisplayName','text','help','options')}
 if isinstance(obj,list):return [non_ui(v) for v in obj]
 return obj
assert non_ui(src)==non_ui(dst),'Non-UI data changed'
destination.parent.mkdir(parents=True,exist_ok=True)
destination.write_text(json.dumps(dst,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert json.loads(destination.read_text(encoding='utf-8'))==dst
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
report={'source_mcm':str(source),'source_sha256':sha(source),'output_mcm':str(destination),'output_sha256':sha(destination),'status':'translated in isolated output, NOT installed','changed_ui_occurrences':counts['translated_fields'],'unchanged_brand':counts['unchanged_brand'],'functional_structure_unchanged':True}
report_path=root/'work'/'fo3'/'mcm_report.json'
report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_mcm','output_mcm')},ensure_ascii=True))
print('MCM_OUTPUT',destination)
