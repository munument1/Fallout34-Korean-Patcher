"""Build a MO2-ready Fallout 34 Korean mod FROM USER-OWNED LOCAL ESMs.

The repository contains only UTF-8 text-field deltas, not converted ESMs.
Select Fallout34.esm; FalloutNV34.esm is expected beside it (or pass --fnv).
The source ESMs are NEVER modified. A new MO2 mod folder includes two newly
localized ESM copies plus prebundled Fallout 4 Korean Interface/Programs/Strings.

Exact verified converter revisions remain the default. Explicit compatibility
mode supports updates that ADD records while preserving known record identity,
original text hashes, and minimum terrain structure.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

from runtime_esm_writer import sha256,write_copy,inspect_structure
from fo4_korean_assets import BUNDLED,select_assets

# In a PyInstaller executable code lives under its temporary extraction path,
# while the canonical data and FO4 resources are shipped BESIDE the EXE.
ROOT=(Path(sys.executable).resolve().parent if getattr(sys,'frozen',False)
      else Path(__file__).resolve().parents[1])
MANIFEST=ROOT/'data'/'canonical'/'manifest.json'
MOD_NAME='Fallout34 Unified Korean'
MINIMUM_MATCH_FRACTION=0.99
# Floor from the converter sources independently checked after the terrain bug.
# Updated builds with less terrain/critical structure are rejected, not patched.
MINIMUM_RECORDS={
    'fo3':{'LAND':47507,'CELL':51821,'WRLD':67,'LTEX':77,'TXST':77,'GRAS':34},
    'fnv':{'LAND':42467,'CELL':44519,'WRLD':34,'LTEX':95,'TXST':95,'GRAS':54},
}


def verify_directory_safety(source_esms:dict[str,Path],output_root:Path):
    resolved=output_root.resolve()
    repo=ROOT.resolve()
    # The source checkout must remain clean, but a standalone EXE may safely
    # create a NEW output folder alongside its own assets. In particular,
    # Desktop and other ancestors of the EXE are not dangerous destinations.
    # The check used to reject every ancestor/descendant of the EXE directory,
    # causing normal choices in the GUI to fail.
    if resolved==repo:
        raise ValueError('Output cannot replace the patcher folder')
    if getattr(sys,'frozen',False):
        # Never stage output inside bundled runtime/data folders.
        for protected in ('_internal','assets','data','licenses'):
            resource=repo/protected
            if resolved==resource or resource in resolved.parents:
                raise ValueError(f'Output cannot be inside bundled resources: {resource}')
    elif repo in resolved.parents:
        raise ValueError('Source checkout is not an output destination; choose another folder')
    for path in source_esms.values():
        src=path.resolve()
        base=src.parent
        # Never place new MO2 assets in the installed FO4/Data directory.
        if resolved==base or base in resolved.parents:
            raise ValueError(f'Output cannot overlap source ESM directory: {base}')
        if base.name.casefold()=='data':
            # The game executable is typically in Data's parent. A new mod
            # should never be staged inside the actual game installation.
            game_root=base.parent
            if resolved==game_root or game_root in resolved.parents:
                raise ValueError(f'Output cannot overlap installed game directory: {game_root}')
    if output_root.exists():raise FileExistsError(f'Output already exists: {output_root}')


def load_canonical(game:str,meta:dict)->tuple[dict,dict]:
    data_file=ROOT/meta['text_field_file']
    if sha256(data_file)!=meta['text_field_file_sha256']:
        raise ValueError(f'Distributed translation dataset altered: {data_file}')
    rows={};counter=collections.Counter();edids={}
    with gzip.open(data_file,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            key=(int(r['id'],16),r['type'],r['field'],int(r['index']))
            original_sha256=r['before_sha256']
            if len(original_sha256)!=64 or any(c not in '0123456789abcdef' for c in original_sha256):
                raise ValueError('Invalid original-field SHA256 in canonical data')
            new=r['korean'].encode('utf-8')+b'\0'
            if key in rows:raise ValueError(f'Duplicate canonical entry {key}')
            if hashlib.sha256(new).hexdigest()==original_sha256 or not new[:-1] or b'\x00' in new[:-1]:
                raise ValueError(f'Invalid canonical entry {key}')
            if '\ufffd' in r['korean'] or not any('\uac00'<=ch<='\ud7a3' for ch in r['korean']):
                raise ValueError(f'Missing or malformed Korean text {key}')
            recordkey=key[:2]
            if recordkey in edids and edids[recordkey]!=r['edid']:
                raise ValueError(f'Conflicting EditorID for record {recordkey}')
            edids[recordkey]=r['edid']
            rows[key]=(original_sha256,new)
            counter[r['type']+':'+r['field']]+=1
    if len(rows)!=meta['text_field_count'] or dict(sorted(counter.items()))!=meta['record_field_counts']:
        raise ValueError('Canonical translation record counts do not match signed manifest')
    return rows,edids


def source_preflight(fo3_path:Path,fnv_path:Path,*,allow_updated_esms:bool=False)->tuple[dict,dict]:
    if not MANIFEST.is_file():raise FileNotFoundError(f'Canonical translation manifest not found: {MANIFEST}')
    manifest=json.loads(MANIFEST.read_text('utf-8'))
    if manifest['schema']!=2:raise ValueError('Unsupported dataset version')
    sources={'fo3':fo3_path,'fnv':fnv_path}
    if len({x.resolve() for x in sources.values()})!=2:raise ValueError('Source paths point to same file')
    for game,path in sources.items():
        meta=manifest['games'][game]
        if not path.is_file() or path.name.casefold()!=meta['esm_filename'].casefold():
            raise FileNotFoundError(f'{game}: expected {meta["esm_filename"]} at {path}')
        current=sha256(path)
        if current!=meta['base_esm_sha256'] and not allow_updated_esms:
            raise ValueError(f'{game}: converter ESM version unsupported. Expected sha256 '
                             f'{meta["base_esm_sha256"]}, actual {current}. '
                             'Use --allow-updated-esms only with NEW original converter builds, '
                             'never old Korean ESMs missing LAND/texture records.')
    select_assets()
    return manifest,sources


def validate_updated_output(game:str,meta:dict,info:dict,dest:Path,*,minimums=None):
    """Fail closed when a new source has broken terrain or incompatible text IDs."""
    record_counts=info['record_type_counts']
    floors=MINIMUM_RECORDS[game] if minimums is None else minimums
    for typ,minimum in floors.items():
        if record_counts.get(typ,0)<minimum:
            raise ValueError(
                f'{game}: updated ESM missing critical {typ} records '
                f'({record_counts.get(typ,0)} < {minimum}). Refusing to release output.')
    structural=inspect_structure(dest)
    if (structural['records']!=info['records'] or
        structural['groups']!=info['groups'] or
        structural['record_type_counts']!=record_counts):
        raise ValueError(f'{game}: updated ESM output structure mismatch')
    applied_fraction=info['changed_fields']/meta['text_field_count']
    if applied_fraction<MINIMUM_MATCH_FRACTION:
        raise ValueError(
            f'{game}: only {info["changed_fields"]:,}/{meta["text_field_count"]:,} '
            f'known text fields matched ({applied_fraction:.2%}). '
            'Converter layout changed too much; manual mapping audit required.')


def build(*,fo3_path:Path,fnv_path:Path,output_root:Path,
          allow_updated_esms:bool=False,progress=print)->dict:
    output_root=output_root.resolve()
    sources={'fo3':fo3_path.resolve(),'fnv':fnv_path.resolve()}
    verify_directory_safety(sources,output_root)
    manifest,sources=source_preflight(
        sources['fo3'],sources['fnv'],allow_updated_esms=allow_updated_esms)
    source_hashes={game:sha256(src) for game,src in sources.items()}

    progress('원본 ESM 및 번역 데이터 무결성 검사 완료')
    # Existing asset selector canonicalizes FO4 CC _ko-only files to _en,
    # never overwrites an _en variant when both are present; it validates
    # 565 bundled sources + the known full terrain converter original hashes.
    assets=select_assets()
    if assets['asset_count']!=505:raise ValueError('FO4 asset list changed unexpectedly')

    output_root.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.fallout34-korean-staging-',dir=output_root.parent))
    success=False
    try:
        mod=temp/MOD_NAME
        mod.mkdir(parents=True,exist_ok=True)
        installed={}
        for game,src in sources.items():
            meta=manifest['games'][game]
            updated=source_hashes[game]!=meta['base_esm_sha256']
            progress(f'{game.upper()} 한글 텍스트 적용 준비: {meta["text_field_count"]:,}개')
            plan,edids=load_canonical(game,meta)
            dest=mod/meta['esm_filename']
            info=write_copy(src,dest,plan,edids,allow_changed=updated)
            if updated:
                validate_updated_output(game,meta,info,dest)
                progress(f'{game.upper()} 업데이트 호환 적용: {info["changed_fields"]:,}건, '
                         f'검토 필요 {info["unmatched_fields"]:,}건')
            elif info['changed_fields']!=meta['text_field_count']:
                raise ValueError(f'{game}: incomplete translation apply')
            verified_hash=sha256(dest)
            if not updated and verified_hash!=meta['verified_local_output_sha256']:
                raise ValueError(f'{game}: patched ESM differs from terrain-preserved independently verified result')
            installed[game]={'esm':meta['esm_filename'],'sha256':verified_hash,
                             'edited_fields':info['changed_fields'],
                             'known_translation_fields':meta['text_field_count'],
                             'unmatched_fields':info['unmatched_fields'],
                             'unmatched_reasons':info['unmatched_reasons'],
                             'unmatched_examples':info['unmatched_examples'],
                             'updated_converter_input':updated,
                             'total_records':info['records'],'total_groups':info['groups'],
                             'critical_record_counts':{
                                 k:info['record_type_counts'].get(k,0)
                                 for k in MINIMUM_RECORDS[game]}}
            if not updated:progress(f'{game.upper()} 검증된 ESM SHA-256 완전 일치')
            del plan,edids

        used=set();copied=0
        for item in assets['assets']:
            relative=Path(item['relative_data_path'].replace('/', '\\'))
            if relative.is_absolute() or '..' in relative.parts or ':' in item['relative_data_path']:
                raise ValueError('Unsafe FO4 bundle resource path')
            target=(mod/relative).resolve()
            if not target.is_relative_to(mod.resolve()):raise ValueError('Output resource outside mod folder')
            unique=target.relative_to(mod.resolve()).as_posix().casefold()
            if unique in used:raise ValueError('Duplicate FO4 bundle resource destination')
            used.add(unique)
            path=BUNDLED/item['source_relative_path'];target.parent.mkdir(parents=True,exist_ok=True)
            if sha256(path)!=item['sha256']:raise ValueError('Bundled source SHA-256 changed')
            shutil.copy2(path,target)
            if sha256(target)!=item['sha256']:raise ValueError('Bundled file copy changed')
            copied+=1
        if copied!=505:raise ValueError(f'FO4 asset count unexpected: {copied}')
        progress(f'폴아웃 4 한국어 Interface·Programs·Strings 파일 {copied}개 구성 완료')

        (mod/'FALLOUT34_KOREAN_README.txt').write_text(
            'Fallout34 + FalloutNV34 + Fallout4 / DLC / CC 한국어 패치\n'
            '이 모드 폴더를 MO2 Mods 경로에 놓고 활성화하세요.\n'
            '원본 Fallout34 및 FalloutNV34 게임 파일, BA2, ESL, Fallout4.esm은 덮어쓰지 않습니다.\n'
            'MO2 다른 한글 폰트/문자열 모드와 중복 로드는 피하고, 우선순위를 확인하세요.\n'
            '원래의 Fallout 34 컨버터 빌드는 엄격 검증합니다. 새 빌드는 호환 옵션으로 확인된 텍스트만 적용됩니다.\n'
            '새로 추가된 문구나 변경된 텍스트는 번역되지 않을 수 있으므로 빌드 보고서를 확인해 주세요.\n'
            'Noto Sans KR SWF 글꼴에 한글 11,172자를 포함했습니다. 화면 폭/줄바꿈은 인게임에서 검수해 주세요.\n'
            '번역 문구 외 원본 지형·메시·자원 데이터는 직접 수정하지 않았습니다.\n',encoding='utf-8-sig')
        # New fields introduced by the converter have no canonical translation
        # and are not counted as "unmatched"; still require user-facing review.
        needs_review=any(x['unmatched_fields'] or x['updated_converter_input']
                         for x in installed.values())
        summary={'version':2,'status':'REVIEW_REQUIRED' if needs_review else 'PASS',
                 'mod_folder_name':MOD_NAME,
                 'translations':installed,'fo4_localization_files':copied,
                 'fo4_cc_conflicting_en_ko_variants_kept_en':assets['conflicting_en_ko_cc_variants_kept_en'],
                 'original_ESMs_modified':False,
                 'input_sha256':source_hashes,
                 'note':('Updated converter build: record identity and original text hashes '
                         'were matched; minimum terrain record counts and output GRUP structure '
                         'were verified. In-game QA and review of unmatched/new texts remain necessary.'
                         if any(x['updated_converter_input'] for x in installed.values()) else
                         'Output ESM SHA-256 matches independently validated full-terrain restoration. Runtime QA is separate.')}
        # A running converter must not replace the input files while we build.
        for game,src in sources.items():
            if sha256(src)!=source_hashes[game]:
                raise ValueError(f'{game}: source ESM changed during patching; discard this output')
        (temp/'build-report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.rename(output_root)
        success=True
        progress(f'MO2 모드 생성 완료: {output_root/MOD_NAME}')
        return summary
    finally:
        if not success and temp.exists():shutil.rmtree(temp)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fo3',required=True,type=Path,help='Select the original Fallout34.esm')
    p.add_argument('--fnv',type=Path,help='FalloutNV34.esm (defaults to same parent as --fo3)')
    p.add_argument('--output',required=True,type=Path,help='New parent folder for mods/Fallout34 Unified Korean output')
    p.add_argument('--allow-updated-esms',action='store_true',
                   help='Try a NEW converter build by matching only unchanged known text. Enforces terrain minimums and >=99%% match.')
    args=p.parse_args()
    fnv=args.fnv or args.fo3.with_name('FalloutNV34.esm')
    print(json.dumps(build(fo3_path=args.fo3,fnv_path=fnv,output_root=args.output,
                           allow_updated_esms=args.allow_updated_esms),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
