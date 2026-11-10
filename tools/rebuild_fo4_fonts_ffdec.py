"""Rebuild three Fallout4 font SWFs with full Hangul, using JPEXS FFDec.

Developer-only tool, not required by end users. Run with verified official
Noto Sans KR OFL-1.1 TTF files (Regular and Bold); full modern Hangul Unicode
coverage 11172/11172. Never mutate old assets until validation passed.
FFDec -replace replaces embedded font outlines, preserves existing font IDs and
font aliases so the FO4 FontConfig.txt references remain intact.
"""
from __future__ import annotations
import argparse,hashlib,json,subprocess
from pathlib import Path

from audit_fo4_swf_glyphs import parse_swf,swf_tags
from preserve_fo4_hud_digits import preserve_hud_digits

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'assets'/'fo4_korean'
WORK=ROOT/'work'/'font_rebuild'/'verified'
FONT_MAP={
    'Interface/fonts_en.swf':{
        3:'bold',      # Brody ornamental font: preserve ID/name, use full Hangul
        6:'regular',   # Share-TechMono terminal
        7:'regular',   # Bold alias; retain the tested Noto face and original HUD digits
        8:'bold',      # Normal alias; retain the existing Noto face
        9:'regular',   # Handwritten_Institute
        10:'regular',  # Arial
        14:'regular',  # Courier New
    },
    'Interface/fonts_console.swf':{
        1:'regular',   # Consolas console
        2:'regular',   # Arial debug
    },
    'Programs/fonts_programs.swf':{
        1:'bold',      # Press Start 2P (PipBoy minigame)
        2:'regular',   # Adventure
        3:'regular',   # vir2L_Medium
        4:'regular',   # Share-TechMono
    },
}
PRESERVE_NON_HANGUL_IDS={'Interface/fonts_en.swf':{4,5}}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for buf in iter(lambda:f.read(1024*1024),b''):h.update(buf)
    return h.hexdigest()


def build(ffdec:Path,regular:Path,bold:Path,output:Path,apply:bool):
    output.mkdir(parents=True,exist_ok=True)
    fonts={'regular':regular,'bold':bold}
    for f in fonts.values():
        if not f.is_file():raise FileNotFoundError(f)
    manifest={'schema':1,'font_license':'SIL Open Font License 1.1 (Noto Sans KR)',
              'font_source':'Google Fonts / Noto Sans KR, local full-syllable TTF',
              'source_ttf_sha256':{k:sha(f) for k,f in fonts.items()},
              'files':{}}
    for rel, mapping in FONT_MAP.items():
        before=SOURCE/rel;dest=output/rel
        if dest.exists():raise FileExistsError(dest)
        dest.parent.mkdir(parents=True,exist_ok=True)
        before_meta=parse_swf(before)
        before_ids={f['font_id']:f for f in before_meta['font_tags']}
        args=[str(ffdec),'-cli','-replace',str(before),str(dest)]
        for font_id,style in mapping.items():
            if font_id not in before_ids:raise ValueError(f'Missing source SWF font {rel}:{font_id}')
            args.extend([str(font_id),str(fonts[style])])
        completed=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                                 errors='replace',timeout=240)
        if completed.returncode!=0 or not dest.exists():
            raise ValueError(f'FFDec failed for {rel}: {completed.stdout[:1800]}')
        if rel=='Interface/fonts_en.swf':
            preserve_hud_digits(before,dest)
        after_meta=parse_swf(dest)
        after_ids={f['font_id']:f for f in after_meta['font_tags']}
        # FFDec intentionally drops obsolete DefineFontAlignZones (73) from
        # replaced fonts. All OTHER non-font assets must remain byte-identical.
        # A single DefineText (11) in the retro Programs SWF is updated by
        # FFDec to remap the replaced font's glyph indices. This is expected
        # only for that file; preserve every ActionScript and unrelated tag.
        excluded=(73,75,11) if rel=='Programs/fonts_programs.swf' else (73,75)
        nonfont_original=[t for t in swf_tags(before) if t[0] not in excluded]
        nonfont_new=[t for t in swf_tags(dest) if t[0] not in excluded]
        if nonfont_original!=nonfont_new:
            raise ValueError(f'FFDec touched non-font script or resource tags: {rel}')
        if rel=='Programs/fonts_programs.swf':
            orig_texts=[t for t in swf_tags(before) if t[0]==11]
            new_texts=[t for t in swf_tags(dest) if t[0]==11]
            if len(orig_texts)!=1 or len(new_texts)!=1:
                raise ValueError('Unexpected retro program font-dependent text structure')
        tag_changed={tag:(before_meta['tag_counts'].get(tag,0),
                          after_meta['tag_counts'].get(tag,0))
                     for tag in set(before_meta['tag_counts'])|set(after_meta['tag_counts'])
                     if before_meta['tag_counts'].get(tag,0)!=after_meta['tag_counts'].get(tag,0)}
        if any(tag!=73 for tag in tag_changed):
            raise ValueError(f'Unexpected SWF tag types changed: {rel}: {tag_changed}')
        old_align={tag[2] for tag in swf_tags(before) if tag[0]==73}
        new_align={tag[2] for tag in swf_tags(dest) if tag[0]==73}
        changed_font_ids={fid.to_bytes(2,'little') for fid in mapping}
        if not new_align.issubset(old_align) or old_align-new_align - changed_font_ids:
            raise ValueError(f'Font alignment tag changed for unrelated glyphs: {rel}')
        if before_ids.keys()!=after_ids.keys():raise ValueError(f'Font ID deleted/added: {rel}')
        for font_id,style in mapping.items():
            a=after_ids[font_id];b=before_ids[font_id]
            if a['font_name']!=b['font_name']:
                raise ValueError(f'Font alias changed: {rel}:{font_id}')
            if a.get('korean_syllable_glyphs')!=11172:
                raise ValueError(f'Full 11172 Hangul not embedded in {rel}:{font_id}, actual {a}')
            if a['number_of_glyphs']<11172:
                raise ValueError('Font contains fewer than full Hangul count')
        for font_id in PRESERVE_NON_HANGUL_IDS.get(rel,set()):
            if before_ids[font_id]!=after_ids[font_id]:
                raise ValueError(f'Controller font accidentally changed {rel}:{font_id}')
        manifest['files'][rel]={'source_sha256':sha(before),'result_sha256':sha(dest),
             'source_bytes':before.stat().st_size,'result_bytes':dest.stat().st_size,
             'replaced_font_ids':{str(k):v for k,v in mapping.items()},
             'embedded_korean_syllables_per_replaced_font':11172}
        if rel=='Interface/fonts_en.swf':
            manifest['files'][rel]['preserved_hud_digits']={'font_id':7,'characters':'0123456789'}
        print('PASS',rel,'full Hangul fonts',len(mapping),'compressed bytes',dest.stat().st_size,flush=True)
    (output/'FONT_REBUILD_REPORT.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if apply:
        # Apply new versioned SWFs only once every test above passed.
        # Original resource bytes remain recoverable in Git; no source TTF is bundled.
        for rel in FONT_MAP:
            (SOURCE/rel).write_bytes((output/rel).read_bytes())
        idx=ROOT/'assets'/'fo4_korean_sources.json'
        bundle=json.loads(idx.read_text('utf-8'))
        for rel in FONT_MAP:
            if bundle['files'][rel]!=manifest['files'][rel]['source_sha256']:
                raise ValueError('Original bundled manifest changed unexpectedly during font swap')
            bundle['files'][rel]=manifest['files'][rel]['result_sha256']
        idx.write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Applied checked SWFs and updated bundled asset index',flush=True)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--ffdec',type=Path,required=True)
    p.add_argument('--regular',type=Path,required=True)
    p.add_argument('--bold',type=Path,required=True)
    p.add_argument('--output',type=Path,default=WORK)
    p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    build(args.ffdec,args.regular,args.bold,args.output,args.apply)
