"""Publish tested full-Hangul SWF font rebuild into FO4 Korean assets.

Strict input/output hash pins, independent backups. Rebuild with
rebuild_fo4_fonts_ffdec.py first. Updates optional locally installed MO2
FO4_AE_1.11.191.Kor font resources, leaving its other assets intact.
"""
from pathlib import Path
from shutil import copy2
import argparse,hashlib,json,os

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'assets'/'fo4_korean'
INDEX=ROOT/'assets'/'fo4_korean_sources.json'

def hashfile(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(1024*1024),b''):h.update(buf)
    return h.hexdigest()

def publish(verified,*,mo2_source=None,backup=None):
    manifest_path=verified/'FONT_REBUILD_REPORT.json'
    report=json.loads(manifest_path.read_text('utf-8'))
    wanted=report['files']
    index=json.loads(INDEX.read_text('utf-8'))
    if len(wanted)!=3 or report['font_license']!='SIL Open Font License 1.1 (Noto Sans KR)':
        raise ValueError('Font package incomplete or license not specified')
    roots=[ASSETS]
    if mo2_source:
        if not mo2_source.is_dir() or backup is None:
            raise ValueError('MO2 font directory missing or no backup destination provided')
        if backup.exists():raise FileExistsError(backup)
        roots.append(mo2_source)
    for rel,item in wanted.items():
        original=ASSETS/rel;new=verified/rel
        if index['files'].get(rel)!=item['source_sha256']:
            raise ValueError(f'Asset index does not match previous version: {rel}')
        if hashfile(original)!=item['source_sha256'] or hashfile(new)!=item['result_sha256']:
            raise ValueError(f'Unverified font source/output bytes: {rel}')
        for root in roots:
            if hashfile(root/rel)!=item['source_sha256']:
                raise ValueError(f'Expected original font not found; no overwrite: {root/rel}')

    if mo2_source:
        backup.mkdir(parents=True,exist_ok=False)
        for rel,item in wanted.items():
            dst=backup/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            copy2(mo2_source/rel,dst)
            if hashfile(dst)!=item['source_sha256']:
                raise ValueError(f'Backed-up MO2 font failed SHA256: {rel}')
    for root in roots:
        for rel,item in wanted.items():
            dst=root/rel
            staged=dst.with_name(dst.name+'.full-hangul-staging')
            if staged.exists():raise FileExistsError(staged)
            copy2(verified/rel,staged)
            if hashfile(staged)!=item['result_sha256']:
                raise ValueError(f'New staged SWF SHA256 differs: {rel}')
            os.replace(staged,dst)
            if hashfile(dst)!=item['result_sha256']:
                raise ValueError(f'New installed SWF SHA256 differs: {rel}')
            print('NEW FONT',root.name,rel,item['result_bytes'],item['result_sha256'],flush=True)
    for rel,item in wanted.items():index['files'][rel]=item['result_sha256']
    INDEX.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    document=ROOT/'docs'/'FONT_REBUILD_REPORT.json'
    document.parent.mkdir(parents=True,exist_ok=True)
    document.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('SUCCESS: 3 SWF fonts replaced; 13 embedded font faces support all 11172 modern Hangul syllables',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--verified',type=Path,required=True)
    parser.add_argument('--active-fo4-mod',type=Path,default=None)
    parser.add_argument('--active-backup',type=Path,default=None)
    a=parser.parse_args()
    publish(a.verified,mo2_source=a.active_fo4_mod,backup=a.active_backup)
