"""Select the existing, already-bundled FO4 Korean CC/DLC/interface resources.

No converter state, game files or old translation work reports are required.
Keep the existing _en sidecar if en/ko variants conflict; select _ko only if
there is no _en version of the same string table. The _en file is required
because Fallout 4 runs with sLanguage=en in the tested English environment.
"""
from pathlib import Path
from collections import defaultdict,Counter
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BUNDLED=ROOT/'assets'/'fo4_korean'
INDEX=ROOT/'assets'/'fo4_korean_sources.json'
STRINGS=re.compile(r'(?i)^(?P<stem>.+)_(?P<lang>en|ko)\.(?P<kind>STRINGS|DLSTRINGS|ILSTRINGS)$')


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()


def select_assets():
    reference=json.loads(INDEX.read_text('utf-8'))
    planned=reference['files']
    actual={}
    for p in BUNDLED.rglob('*'):
        if not p.is_file():continue
        if p.is_symlink() or not p.resolve().is_relative_to(BUNDLED.resolve()):
            raise ValueError('Symbolic link escaping bundle')
        name=p.relative_to(BUNDLED).as_posix()
        actual[name]=sha256(p)
    if actual!=planned:raise ValueError('FO4 Korean assets missing, stale or modified; check index')
    if len(actual)!=565:raise ValueError('FO4 bundle source count not expected')

    chosen={};variants=defaultdict(dict)
    for name,digest in sorted(actual.items()):
        parts=Path(name).parts
        if len(parts)<2 or parts[0].casefold() not in ('interface','programs','strings'):
            raise ValueError(f'Unexpected bundled resource path {name}')
        row={'relative_data_path':name,'source_relative_path':name,'sha256':digest}
        mt=STRINGS.fullmatch(parts[-1])
        if parts[0].casefold()=='strings' and mt and mt['stem'].lower().startswith('cc'):
            output_name='Strings/'+mt['stem']+'_en.'+mt['kind']
            row['relative_data_path']=output_name
            variants[output_name.casefold()][mt['lang'].lower()]=row
        else:
            key=name.casefold()
            if key in chosen:raise ValueError(f'Duplicate output path {name}')
            chosen[key]=row
    conflict=0;ko_renamed=0
    for key,versions in variants.items():
        en=versions.get('en');ko=versions.get('ko')
        if en and ko and en['sha256']!=ko['sha256']:conflict+=1
        if en:row=en
        elif ko:row=ko;ko_renamed+=1
        else:raise ValueError('Unreachable CC variant')
        if key in chosen:raise ValueError(f'Conflicting output resource {key}')
        chosen[key]=row
    if len(chosen)!=505 or conflict!=33:
        raise ValueError(f'Unexpected current FO4 asset selectors: count={len(chosen)}, conflicts={conflict}')
    essential={'interface/fonts_en.swf','interface/fonts_console.swf',
               'strings/fallout4_en.strings','strings/fallout4_en.dlstrings',
               'strings/fallout4_en.ilstrings'}
    if not essential.issubset(chosen.keys()):
        raise ValueError('Bundled critical font or translation file is missing')
    return {'assets':sorted(chosen.values(),key=lambda r:r['relative_data_path'].casefold()),
            'asset_count':len(chosen),'conflicting_en_ko_cc_variants_kept_en':conflict,
            'ko_only_cc_tables_renamed_to_en':ko_renamed}
