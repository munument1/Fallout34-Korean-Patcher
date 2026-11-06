"""Classify actual user-display field strings that are NOT covered by planned Korean assignments.
Read only; create per-category review files. Same English in different contexts is never automatically patched here.
"""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,importlib.util,json,re,hashlib
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
dict_file=ROOT/'tools'/'read_xtranslator_sst.py'
spec=importlib.util.spec_from_file_location('sst_parser',dict_file)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
folder=Path('F:/\ubc88\uc5ed/\ud504\ub85c\uadf8\ub7a8/xTranslator/UserDictionaries/FalloutNV')
names={'fo3':['fallout3','anchorage','thepitt','brokensteel','pointlookout','zeta'],
       'fnv':['falloutnv','deadmoney','honesthearts','oldworldblues','lonesomeroad','gunrunnersarsenal','caravanpack','classicpack','mercenarypack','tribalpack']}
PREFERRED={
 ('INFO','RNAM'):[('DIAL','FULL'),('INFO','RNAM'),('INFO','NAM1')],
 ('INFO','NAM1'):[('INFO','NAM1'),('INFO','RNAM'),('DIAL','FULL')],
 ('TERM','UNAM'):[('NOTE','TNAM'),('TERM','UNAM'),('TERM','DESC'),('TERM','ITXT')],
 ('TERM','BTXT'):[('TERM','DESC'),('TERM','ITXT'),('NOTE','TNAM')],
 ('TERM','ITXT'):[('TERM','ITXT'),('TERM','DESC'),('TERM','RNAM')],
 ('TERM','FULL'):[('TERM','FULL'),('NOTE','FULL'),('NOTE','EDID')],
 ('NOTE','FULL'):[('NOTE','FULL')],
 ('MESG','ITXT'):[('MESG','ITXT'),('MESG','DESC')],
 ('MESG','DESC'):[('MESG','DESC')],
 ('QUST','FULL'):[('QUST','FULL')],
 ('QUST','CNAM'):[('QUST','CNAM')],
 ('LSCR','DESC'):[('LSCR','DESC')],
}
FLAGS_INTERNAL={
 'QUST/FULL':'Often editor/debug quest name. Quest journal objective is QUST/CNAM.',
 'FACT/FULL':'Faction internal name; may display in reputation and rank contexts.',
 'SPEL/FULL':'Many passive/internal effect and ability names.',
 'MGEF/FULL':'Often editor/internal effect name.',
 'NOTE/FULL':'Often generated note internal title; may not show to player.',
 'TERM/FULL':'Terminal title could be visible; some internal name strings.',
 'NPC_/FULL':'Test NPC names and hidden actors may not render.',
}
TOKEN=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}')
def valid_ko(en,ko):
 return en!=ko and bool(ko.strip()) and Counter(TOKEN.findall(en))==Counter(TOKEN.findall(ko))
for game,stem in names.items():
    tm=defaultdict(set);typed=defaultdict(set);plug=defaultdict(set);sources=defaultdict(set)
    for name in stem:
        p=folder/(name+'_en_ko.sst')
        if not p.is_file():continue
        s=m.parse_sst(p);masters=[x.casefold() for x in s['master_files']]
        for r in s['records']:
            en=r['source'];ko=r['korean']
            if not en or not ko or en==ko:continue
            idnum=int(r['form_id'],16)
            plugin=masters[idnum>>24] if idnum>>24<len(masters) else '?'
            value=(r['record_name'],r['field_name'],en)
            tm[en].add(ko);typed[value].add(ko)
            plug[(plugin,en)].add(ko)
            sources[value].add((plugin,f'{idnum&0xffffff:06x}'))
    out=ROOT/'data'/game
    input_name=out/'visible_residual_candidates.jsonl.gz'
    key_origins={}
    if game=='fnv':
        kpath=out/'converter_origin_keys_selected.tsv.gz'
        pat=re.compile(r'(?i)^([a-z0-9._ \-]+\.esm):([a-f0-9]{6})$')
        with gzip.open(kpath,'rt',encoding='utf-8') as f:
            for line in f:
                sp=line.rstrip('\n').split('\t',3)
                if len(sp)!=4 or sp[0]=='formid':continue
                origin=[k.lower() for k in sp[3].split('|') if pat.fullmatch(k)]
                if origin:key_origins[sp[0]]=origin
    # Need index origin+text in addition to same English.
    exact_origin=defaultdict(set)
    for key,links in sources.items():
        tp,field,en=key
        for plugin,low in links:
            exact_origin[(plugin+':'+low,en)].update(typed[key])
    rows=Counter();by_field=defaultdict(Counter);untranslated_unique=defaultdict(set);sample=defaultdict(list);safe=[];review=[]
    with gzip.open(input_name,'rt',encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            en=r['english'];key=(r['record_type'],r['field']);label='/'.join(key)
            origins=key_origins.get(r['target_formid'],[])
            src_pairs=[(x,exact_origin[(x,en)]) for x in origins if (x,en) in exact_origin]
            distinct_origin=set().union(*(v for _,v in src_pairs)) if src_pairs else set()
            preferred=PREFERRED.get(key,[key])
            preferred_ko=[(t,f,typed[(t,f,en)]) for t,f in preferred if typed.get((t,f,en))]
            # Prefer exact provenance; if absent, choose matching type/field from original SSTs
            if len(distinct_origin)==1:status='converter_origin_unique_ko';options=distinct_origin
            elif len(distinct_origin)>1:status='converter_origin_conflicting_ko';options=distinct_origin
            elif preferred_ko:
                allvals=set().union(*(v for _,_,v in preferred_ko))
                if len(allvals)==1:status='preferred_original_field_unique_ko';options=allvals
                else:status='preferred_original_field_conflicting_ko';options=allvals
            elif en in tm:
                allvals=tm[en]
                if len(allvals)==1:status='other_field_unique_ko';options=allvals
                else:status='other_field_conflicting_ko';options=allvals
            else:status='no_translation_in_current_sst';options=set()
            if status.endswith('unique_ko') and not valid_ko(en,next(iter(options))):
                status='markup_conflict_after_reuse'
            r['translation_status']=status;r['matched_origins']=[x for x,_ in src_pairs[:8]]
            if options and len(options)==1:r['suggested_korean']=next(iter(options))
            elif options:r['korean_variant_count']=len(options)
            r['screen_display_note']=FLAGS_INTERNAL.get(label,'Likely displayed in game when referenced')
            rows[status]+=1;by_field[label][status]+=1
            untranslated_unique[status].add((label,en))
            if len(sample[(label,status)])<4:sample[(label,status)].append({'formid':r['target_formid'],'english':en[:135],'ko':r.get('suggested_korean'),'original_ids':r['matched_origins'][:3]})
            if status in ('converter_origin_unique_ko','preferred_original_field_unique_ko'):safe.append(r)
            else:review.append(r)
    with gzip.open(out/'visible_reuse_candidates.jsonl.gz','wt',encoding='utf-8',compresslevel=6) as f:
        for r in safe:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    with gzip.open(out/'visible_manual_review.jsonl.gz','wt',encoding='utf-8',compresslevel=6) as f:
        for r in review:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    report={
       'game':game,
       'scope':'currently-uncovered potentially visible fields, not runtime-certified strings',
       'original_sst_count':len(stem),'counts':dict(rows),
       'distinct_by_field_and_english_by_status':{k:len(v) for k,v in untranslated_unique.items()},
       'by_field':{label:dict(c) for label,c in by_field.items()},
       'samples':{f'{a}|{b}':v for (a,b),v in sample.items()},
       'key_source_index_target_ids':len(key_origins),
       'note':'Source exact match if possible, else original field preference. These are translation recovery candidates only. Actual runtime reachability and patch generation are separate.'
    }
    (out/'visible_reuse_triage_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('GAME',game,'CATEGORIES',dict(rows),flush=True)
    for k,v in sorted(by_field.items(),key=lambda kv:-sum(kv[1].values()))[:15]:
        print('FIELD',k,'COUNT',sum(v.values()),'STATUS',dict(v),flush=True)
