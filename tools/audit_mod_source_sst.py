from pathlib import Path
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
keys=['streetlight','dcinterior','interior light','lighting','dcstreet']
for k in keys:
 ms=[p.name for p in folder.glob('*.sst') if k in p.stem.lower()]
 print(k,ms)
