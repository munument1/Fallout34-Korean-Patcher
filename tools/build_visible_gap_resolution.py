"""Build a priority residual queue, plus tier-A patch assignments with exact source provenance or generated UI template.
Tier B is NOT included in the patch plan: same original field and unique Korean text without a proven FormID link.
"""
from pathlib import Path
from collections import Counter,defaultdict
import gzip,json,csv,re,hashlib
ROOT=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
TOKEN=re.compile(r'%[A-Za-z_][A-Za-z0-9_]*%|(?<!%)%(?:\d+\$)?[-+.#0-9]*[diufsg]|&[A-Za-z_][A-Za-z0-9_]*;|<Global=[^>]{1,120}>|</?(?:b|i|u|font|color|size)(?:[ =][^<>]{0,70})?>|\{\w+\}')
PRIORITIES={
 'INFO/RNAM':'P0_dialogue_option',
 'INFO/NAM1':'P0_dialogue_subtitle',
 'TERM/UNAM':'P0_terminal_body',
 'TERM/ITXT':'P0_terminal_option',
 'TERM/BTXT':'P0_terminal_display',
 'TERM/FULL':'P1_terminal_title',
 'MESG/DESC':'P0_popup_message',
 'MESG/ITXT':'P0_popup_choice',
 'MESG/FULL':'P1_message_title',
 'QUST/CNAM':'P0_quest_objective',
 'LSCR/DESC':'P1_loadscreen',
 'NPC_/FULL':'P1_actor_name',
 'ARMO/FULL':'P1_item_name',
 'WEAP/FULL':'P1_item_name',
 'MISC/FULL':'P1_item_name',
 'KEYM/FULL':'P1_item_name',
 'PERK/FULL':'P1_perk_name',
 'PERK/DESC':'P1_perk_description',
 'CELL/FULL':'P1_area_name',
 'WRLD/FULL':'P1_world_name',
 'NOTE/FULL':'P2_note_name_maybe_internal',
 'FACT/FULL':'P2_faction_name_possible',
 'SPEL/FULL':'P2_spell_effect_possible',
 'MGEF/FULL':'P2_magic_effect_possible',
 'QUST/FULL':'P2_quest_editor_name_maybe_internal',
}
def key(r):
 return (r['target_formid'],r['record_type'],r['field'],int(r.get('target_field_occurrence_index',r.get('field_index',0))))
def safe(r):
 a=r['english'];b=r['korean']
 return bool(b) and b!=a and Counter(TOKEN.findall(a))==Counter(TOKEN.findall(b))
def save_gz(path,rows):
 with gzip.open(path,'wt',encoding='utf-8',compresslevel=6) as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
for game in ('fo3','fnv'):
 d=ROOT/'data'/game
 base={}
 with gzip.open(d/'indexed_patch_plan_candidates.jsonl.gz','rt',encoding='utf-8') as f:
  for line in f:
   r=json.loads(line);base[key(r)]=r
 strict={};reject=Counter()
 def add(r,source,ko):
  rr=dict(r);rr['korean']=ko
  rr['target_field_occurrence_index']=rr.get('field_index',rr.get('target_field_occurrence_index'))
  rr['plan_source']=source
  k=key(rr)
  if not safe(rr):reject['placeholder_or_same_text']+=1;return
  if k in base:
   if base[k]['english']!=rr['english'] or base[k]['korean']!=ko:reject['conflicts_existing_plan']+=1
   else:reject['already_covered']+=1
   return
  if k in strict:
   if strict[k]['english']!=rr['english'] or strict[k]['korean']!=ko:
    reject['strict_conflict']+=1
    strict.pop(k,None)
   else:reject['strict_duplicate']+=1
   return
  strict[k]=rr
 # Source-ID normalized edits
 for line in gzip.open(d/'normalized_source_id_matches.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line);add(r,'same_source_id_editor_directions_removed',r['suggested_korean'])
 # New generated choice for paginated lists, exact English unique and conventional translation
 for line in gzip.open(d/'visible_manual_review.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line)
  if r['record_type']=='INFO' and r['field']=='RNAM' and r['english']=='More...':
   add(r,'converter_generated_more_button','더 보기...')
 # Source-anchored added skill prefix
 for line in gzip.open(d/'skill_source_verified_suggestions.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line);add(r,'same_source_id_added_skill_prefix',r['korean'])
 # Converter-created perk ranks use existing original PERK/FULL name plus a numeric suffix.
 if game=='fnv':
  for line in gzip.open(d/'ranked_perk_source_verified.jsonl.gz','rt',encoding='utf-8'):
   r=json.loads(line)
   add(r,'converter_generated_perk_rank_suffix',r['korean'])
 # For tier B, do not modify candidate patch plan automatically
 tier_b={}
 for line in gzip.open(d/'visible_reuse_candidates.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line)
  if r.get('translation_status')!='preferred_original_field_unique_ko':continue
  k=key(r)
  if k not in base and k not in strict: tier_b.setdefault(k,r)
 # Medium confidence: skill english-only, and editor-direction normalization exact text no proven source id
 for extra_file in ('skill_text_only_suggestions.jsonl.gz','normalized_dialogue_review.jsonl.gz'):
  for line in gzip.open(d/extra_file,'rt',encoding='utf-8'):
   r=json.loads(line)
   if extra_file=='normalized_dialogue_review.jsonl.gz' and r.get('editor_normalize_class')!='same_dialogue_field_editor_cues_stripped_unique_ko':continue
   k=key(r)
   if k in base or k in strict:continue
   ko=r.get('korean') if extra_file.startswith('skill') else r.get('suggested_korean')
   if not ko:continue
   if not safe({'english':r['english'],'korean':ko}):continue
   r['suggested_korean']=ko
   tier_b.setdefault(k,r)
 # Need actual visible residual rows (not inferred), with original uncovered list as source of truth
 unhandled=defaultdict(lambda:{'occurrences':0,'ids':[],'status':'missing_korean','text':'','tier':'','category':''})
 summary=Counter();categories=defaultdict(Counter);distinct=defaultdict(set)
 for line in gzip.open(d/'visible_residual_candidates.jsonl.gz','rt',encoding='utf-8'):
  r=json.loads(line)
  k=key(r);label=r['record_type']+'/'+r['field']
  owning='fallout4_base' if int(r['target_formid'],16)>>24==0 else 'fallout34_converted'
  if k in base:state='existing_covered'
  elif k in strict:state='strict_recovered'
  elif k in tier_b:state='unique_korean_context_review'
  elif owning=='fallout4_base':state='external_fo4_base_text'
  else:state='needs_new_translation_or_other_source'
  summary[state]+=1;categories[label][state]+=1
  if state in ('strict_recovered','unique_korean_context_review','needs_new_translation_or_other_source'):
   distinct[(label,state)].add(r['english'])
  if state=='needs_new_translation_or_other_source':
   ident=(r['record_type'],r['field'],r['english'])
   cell=unhandled[ident]
   cell['occurrences']+=1
   if len(cell['ids'])<4:cell['ids'].append(r['target_formid'])
   cell['text']=r['english']
   cell['category']=r['screen_category']
   cell['tier']=PRIORITIES.get(label,'P2_other')
   cell['status']=state
 # Need grouping for only high priority and likely visible
 high=[(k,v) for k,v in unhandled.items() if v['tier'].startswith('P0') or v['tier'].startswith('P1')]
 high.sort(key=lambda item:(item[1]['tier'], -item[1]['occurrences'], -len(item[1]['text'])))
 csv_file=d/'visible_translation_backlog.csv'
 with csv_file.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f)
  w.writerow(['priority','record_type','field','screen_category','untranslated_occurrences','english','example_formids','review_state','korean'])
  for (typ,field,en),v in high:
   w.writerow([v['tier'],typ,field,v['category'],v['occurrences'],en,';'.join(v['ids']),v['status'],''])
 all_file=d/'visible_translation_backlog_all.jsonl.gz'
 save_gz(all_file,({'record_type':k[0],'field':k[1],'english':k[2],**v} for k,v in unhandled.items()))
 save_gz(d/'indexed_patch_plan_v2_strict_extra.jsonl.gz',strict.values())
 save_gz(d/'visible_reuse_context_review.jsonl.gz',tier_b.values())
 report={
  'game':game,
  'base_plan_count':len(base),
  'strict_additions':len(strict),
  'strict_additions_by_method':dict(Counter(v['plan_source'] for v in strict.values())),
  'medium_context_review_count':len(tier_b),
  'remaining_non_captured_visible_occurrences':summary['needs_new_translation_or_other_source'],
  'remaining_distinct_record_type_field_english':len(unhandled),
  'remaining_p0_p1_unique_english_field_pairs':len(high),
  'state_counts':dict(summary),
  'distinct_english_by_field_status':{f'{k[0]}|{k[1]}':len(v) for k,v in distinct.items()},
  'by_field':{lab:dict(c) for lab,c in categories.items()},
  'strict_qa_rejections':dict(reject),
  'backlog_csv':str(csv_file),
  'warning':'No ESP/STRINGS generated. P0/P1 are possibly visible strings, not verified runtime reachability. Tier-B matches are not automatically applied; all remaining entries require source provenance, scope and context checks.'
 }
 (d/'visible_gap_resolution_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('REPORT',game,json.dumps({k:v for k,v in report.items() if k not in ('by_field','distinct_english_by_field_status','backlog_csv','warning')},ensure_ascii=True),flush=True)
 print('TOP BACKLOG',[(k[0]+'/'+k[1],str(k[2])[:90],v['occurrences']) for k,v in high[:16]],flush=True)
