from pathlib import Path
import json
r=Path(r'D:\Codex_Trans\Fallout34-KR-Patcher\data')
for game in ('fo3','fnv'):
 v=json.loads((r/game/'visible_gap_resolution_report.json').read_text(encoding='utf-8'))
 print('GAME',game)
 for field,counts in sorted(v['by_field'].items(),key=lambda x:-x[1].get('needs_new_translation_or_other_source',0))[:26]:
  print(' FIELD',field,'NEEDS_NEW',counts.get('needs_new_translation_or_other_source',0),'REUSE_REVIEW',counts.get('unique_korean_context_review',0),'STRICT',counts.get('strict_recovered',0))
