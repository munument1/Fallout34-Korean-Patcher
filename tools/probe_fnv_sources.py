from pathlib import Path
import csv,struct,hashlib,json,importlib.util,collections
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
s=Path(r'C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fnv')
esm=s/'staging'/'Data'/'FalloutNV34.esm'
with esm.open('rb') as f: head=f.read(24)
sig,size,flags,*rest=struct.unpack('<4sIIIII',head)
print('ESM',sig,'flags',hex(flags),'localized',bool(flags&0x80),'bytes',esm.stat().st_size)
fields=collections.Counter();plugins=collections.Counter();direct=collections.Counter();sampling={}
mapfile=s/'work'/'reports'/'formid_map.tsv'
with mapfile.open('r',encoding='utf-8') as f:
 for row in csv.DictReader(f,delimiter='\t'):
  plugins[row['source'].split(':')[0]]+=1;fields[row['type']]+=1
  name,rid=row['source'].split(':',1)
  if len(sampling.get(name,[]))<2:sampling.setdefault(name,[]).append(row)
  if int(row['formid'],16)&0xffffff==int(rid,16):direct[name]+=1
print('MAP PLUGINS',plugins.most_common(), 'TYPES',fields.most_common(15))
print('DIRECT LOCAL ID SAME',direct,'EXAMPLES',json.dumps(sampling,ensure_ascii=True)[:2300])
read=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\tools\read_xtranslator_sst.py')
spec=importlib.util.spec_from_file_location('reader',read);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
for name in ('falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal','caravanpack','classicpack','mercenarypack','tribalpack'):
 p=folder/(name+'_en_ko.sst')
 if not p.is_file():print('MISSING_SST',p.name);continue
 sst=mod.parse_sst(p)
 counts=collections.Counter()
 for row in sst['records']:
  mid=int(row['form_id'],16)>>24
  if mid<len(sst['master_files']):
   counts[sst['master_files'][mid].casefold()]+=1
 print('SST',p.name,'total',len(sst['records']),'masters',sst['master_files'],'types',counts.most_common(9))
