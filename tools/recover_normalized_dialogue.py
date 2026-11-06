"""Match unlinked visible dialogue to SST after removing non-rendered editor-direction braces.
Provenance exact same source FormID required for automatic-ready group.
Prefix skill checks require REVIEW until label/variable mapping is proven.
"""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,json,re,importlib.util
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
sspec=importlib.util.spec_from_file_location('sst',ROOT/'tools'/'read_xtranslator_sst.py')
sst=importlib.util.module_from_spec(sspec);sspec.loader.exec_module(sst)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
games={'fo3':['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta'],
       'fnv':['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal','caravanpack','classicpack','mercenarypack','tribalpack']}
def clean(text):
    # Braces at the *beginning* only: dialogue acting notes stored in SST but removed by converter.
    x=text.lstrip('\ufeff')
    x=re.sub(r'^\s*(?:\{[^{}]{1,160}\}\s*)+', '',x)
    return x.strip()
def split_skill(text):
    x=re.sub(r'^\s*\[[^\]]{2,120}\]\s*','',text, count=1)
    return x.strip()
for game,names in games.items():
    by_origin=defaultdict(lambda:defaultdict(set))
    by_text=defaultdict(set)
    by_type=defaultdict(set)
    for name in names:
        parsed=sst.parse_sst(folder/(name+'_en_ko.sst'))
        masters=[x.casefold() for x in parsed['master_files']]
        for r in parsed['records']:
            fid=int(r['form_id'],16)
            mid=fid>>24
            if mid>=len(masters):continue
            plugin=masters[mid]
            if not r['korean'] or r['korean']==r['source']:continue
            if r['record_name'] not in ('INFO','DIAL','TERM','NOTE','MESG'):continue
            english=clean(r['source'])
            if not english:continue
            source=f'{plugin}:{fid&0xffffff:06x}'
            by_origin[(source,r['record_name'],r['field_name'],english)][r['korean']].add(r['source'])
            by_text[english].add(r['korean'])
            by_type[(r['record_name'],r['field_name'],english)].add(r['korean'])
    out=ROOT/'data'/game
    generated_origins=defaultdict(list)
    if game=='fnv':
        pat=re.compile(r'(?i)^([a-z0-9._ \-]+\.esm):([a-f0-9]{6})$')
        with gzip.open(out/'converter_origin_keys_selected.tsv.gz','rt',encoding='utf-8') as f:
            for line in f:
                sp=line.rstrip('\n').split('\t',3)
                if len(sp)!=4:continue
                for v in sp[3].split('|'):
                    if pat.fullmatch(v):generated_origins[sp[0]].append(v.casefold())
    status=Counter();byfield=defaultdict(Counter);samples=defaultdict(list);high=[];review=[]
    for line in gzip.open(out/'visible_manual_review.jsonl.gz','rt',encoding='utf-8'):
        r=json.loads(line)
        if r['translation_status'] not in ('no_translation_in_current_sst','markup_conflict_after_reuse'):continue
        tp,field=r['record_type'],r['field']
        if tp not in ('INFO','DIAL','TERM','NOTE','MESG'):continue
        e=r['english']
        # Main game's original local ID preserved for 0x010xxxxx (but use only as a probe)
        formid=int(r['target_formid'],16)
        ids=generated_origins.get(r['target_formid'],[])
        if 0x01000000<=formid<0x01100000:
            ids.append(('fallout3.esm' if game=='fo3' else 'falloutnv.esm')+f':{formid&0xffffff:06x}')
        if game=='fnv' and 0x01100000<=formid<0x01800000:
            ids.append('falloutnv.esm:'+f'{formid&0xffffff:06x}')
        ids=list(dict.fromkeys(ids))
        # INFO/NAM1 is VO response; DIAL/FULL is topic/player line. Trim acting cues.
        preferred=[(tp,field)]
        if (tp,field)==('INFO','RNAM'):preferred=[('DIAL','FULL'),('INFO','RNAM'),('INFO','NAM1')]
        elif (tp,field)==('INFO','NAM1'):preferred=[('INFO','NAM1'),('DIAL','FULL'),('INFO','RNAM')]
        origin_candidates=defaultdict(set)
        for origin in ids:
            for t,f in preferred:
                for ko,orig_en in by_origin.get((origin,t,f,e),{}).items():origin_candidates[ko].update(orig_en)
        if len(origin_candidates)==1:
            cls='source_id_editor_cues_stripped_exact'
            ko=next(iter(origin_candidates))
        elif len(origin_candidates)>1:
            cls='same_source_multiple_korean'
            ko=None
        else:
            candidates=set()
            for t,f in preferred:candidates.update(by_type[(t,f,e)])
            if len(candidates)==1:
                cls='same_dialogue_field_editor_cues_stripped_unique_ko'
                ko=next(iter(candidates))
            elif len(candidates)>1:
                cls='same_dialogue_field_ko_conflict';ko=None
            else:
                suffix=split_skill(e)
                tags=len(e)-len(suffix)
                if suffix!=e:
                    cc=set()
                    for t,f in preferred:cc.update(by_type[(t,f,suffix)])
                    if len(cc)==1:
                        cls='skill_prefix_added_to_original_english';ko=next(iter(cc))
                    elif len(cc)>1:
                        cls='skill_prefix_korean_conflict';ko=None
                    else:cls='still_no_editor_normalized_sst_match';ko=None
                else:cls='still_no_editor_normalized_sst_match';ko=None
        status[cls]+=1;byfield[f'{tp}/{field}'][cls]+=1
        if len(samples[cls])<5:samples[cls].append({'target':r['target_formid'],'english':e[:140],'ko':(ko or '')[:140],'origin_keys':ids[:3]})
        row=dict(r);row['editor_normalize_class']=cls;row['original_source_keys']=ids
        if ko:row['suggested_korean']=ko
        if cls=='source_id_editor_cues_stripped_exact':high.append(row)
        else:review.append(row)
    def write(name,rows):
        with gzip.open(out/name,'wt',encoding='utf-8',compresslevel=6) as f:
            for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    write('normalized_source_id_matches.jsonl.gz',high)
    write('normalized_dialogue_review.jsonl.gz',review)
    report={'game':game,'statuses':dict(status),'by_dialogue_field':{k:dict(v) for k,v in byfield.items()},'examples':dict(samples),'note':'No ESP writes. Braced direction stripped only from source English at start; retained variable tags in target must not be changed unless validated.'}
    (out/'normalized_dialogue_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('GAME',game,'MATCH',dict(status),flush=True)
    for typ,st in byfield.items():print('FIELD',typ,dict(st),flush=True)
    print('EXAMPLES',json.dumps({k:v[:2] for k,v in samples.items()},ensure_ascii=True)[:4000],flush=True)
