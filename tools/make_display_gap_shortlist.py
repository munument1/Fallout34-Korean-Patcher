from pathlib import Path
import csv,collections
root=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher')
fields=[('INFO','NAM1','NPC 발화'),('INFO','RNAM','대화 선택지'),('TERM','UNAM','터미널 본문'),('TERM','ITXT','터미널 선택지'),
 ('MESG','DESC','안내/알림'),('MESG','ITXT','알림 선택지'),('QUST','CNAM','퀘스트 목표'),('MISC','FULL','잡동사니 이름'),
 ('ARMO','FULL','방어구 이름'),('KEYM','FULL','열쇠 이름'),('PERK','FULL','퍽 이름'),('PERK','DESC','퍽 설명'),('CELL','FULL','지역 이름')]
lines=['# 실제 화면 출력 가능성이 있는 한글 미연결 목록','',
'이 문서는 **현재 번역 데이터에 없는 콘텐츠를 검토하는 작업 목록**입니다. 게임에서 호출된 적이 확인된 문구의 목록은 아닙니다. UI 외부 엔진/스크립트, 별도 모드 콘텐츠는 추가 검사가 필요합니다.',
'','정확한 모든 항목은 data/{fo3,fnv}/visible_translation_backlog.csv에 있습니다. 고유 영문은 레코드 종류 + 필드 + 영문으로 식별합니다.','']
for game in ('fo3','fnv'):
 path=root/'data'/game/'visible_translation_backlog.csv'
 by=collections.defaultdict(list);totals=collections.Counter()
 with path.open('r',encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   k=(r['record_type'],r['field'])
   totals[k]+=1
   if len(by[k])<8:by[k].append(r)
 lines.extend(['## '+('폴아웃 3 및 DLC' if game=='fo3' else '뉴베가스 및 DLC'),''])
 for tp,field,label in fields:
  current=by.get((tp,field),[])
  if not current:continue
  lines.extend(['### '+label+' ('+tp+'/'+field+')','고유 영문·필드 조합 중 새 번역 또는 추가 번역 자료가 필요한 후보: **'+str(totals[(tp,field)])+'건**.',''])
  for row in current[:4]:
   english=' '.join(row['english'].split()).replace('|','\\|')
   lines.append('- '+row['example_formids'].split(';')[0]+' · '+str(row['untranslated_occurrences'])+'회 · '+english[:155])
  lines.append('')
(root/'DISPLAY_GAPS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('WROTE',(root/'DISPLAY_GAPS.md'),len(lines),'lines')
