> **최근 현황:** [STATUS.md](STATUS.md) — **최우선은 남아 있는 인게임 미번역의 복구·신규 번역**입니다. 2026-11-06 기준 기존 SST 재연결, 단일 INFO 레코드 내부 자막/선택지 누락, 명확한 화면 문구 직접 번역을 통해 추가 40,135개 필드의 번역 계획을 복구했습니다. **완역 전에는 ESM 미리보기/설치본을 추가로 만들지 않습니다.** 범위는 FO3/FNV 두 변환 ESM에 한정하며, **F34Online.esp와 온라인 기능은 번역 대상에서 제외합니다.** 아래에는 이전 작업 이력도 포함돼 있습니다.

# Fallout34 Korean Patcher — FO3 번역 데이터 작업

Fallout34 v0.9.33의 폴아웃 3 본편 및 DLC 변환 결과물을 대상으로 기존 xTranslator 한국어 SST 데이터를 매핑한 독립 작업 공간입니다.

> **검증된 로컬 ESM 미리보기:** FO3와 FNV의 한국어 ESM 복사본을 별도로 생성해 모든 레코드·필드에 대한 독립 정적 검증을 통과했습니다. 그러나 **실제 게임에서 실행해 본 것은 아니므로 완역·정상 실행은 미확정**입니다. 설치된 원본 ESM 및 F드라이브 원본 사전은 수정하지 않습니다. ESM 바이너리는 게임 자산이므로 GitHub에 올리거나 재배포하지 않습니다.

## 원문 자료

- Fallout34 변환 ESM: `C:\Games\Steam\steamapps\common\Fallout 4\Fallout34_Work\fo3\staging\Data\Fallout34.esm`
- ESM SHA256: `be0e7f25d0a28c672de2c12afbbf402bff0bb202037c231930d4649afd138603`
- 변환 원본 ID 매핑: `Fallout34_Work\fo3\work\reports\formid_map.tsv` (321,102행)
- 번역 원본: `F:\번역\프로그램\xTranslator\UserDictionaries\FalloutNV\`
- 대상 SST: `fallout3_en_ko.sst`, `anchorage_en_ko.sst`, `thepitt_en_ko.sst`, `brokensteel_en_ko.sst`, `pointlookout_en_ko.sst`, `zeta_en_ko.sst`.

## 중요: 폴아웃 3 본편 FormID 특성

`formid_map.tsv`에는 폴아웃 3 본편의 직접 매핑이 19건밖에 없었습니다. 대부분 본편 FormID는 기존 하위 24비트에 `0x01000000`을 더하는 구조였습니다. 이 규칙을 가정하기만 하지 않고 **Fallout34.esm에서 FormID·레코드 종류·필드·영문 원문을 모두 일치 확인한 항목만** 복구했습니다. DLC는 `formid_map.tsv`의 명시적 매핑을 우선했습니다.

| 집계 | 건수 |
|---|---:|
| 기존 FO3+5 DLC SST 중 FO3 원문과 연결된 항목 | 51,872 |
| 초기 직접 매핑 후보 | 14,406 |
| 초기 중복 제거·검증 통과 | 11,946 |
| 신규 FO3 본편 자동 연결 중 원문까지 정확히 일치 | 33,552 |
| 추가 복구 후 중복 제거·검증 통과 | **45,179** |
| 기존 대비 순증 | **33,233** |
| 직접 복구 원문이 아닌 항목(필드 누락 등) | 3,810 |
| DLC에서 직접 매핑 누락된 항목 | 104 |
| 초기 직접 매핑 원문 검증에서 제외된 항목 | 2,318 |

같은 번역 항목의 중복 319행은 통합했고, 한국어 충돌 키는 없었습니다. **45,179는 실제 플러그인에 적용된 수가 아니라 패처에서 사용할 수 있는 우선 검증 후보 수입니다.** `INFO` 응답 인덱스와 반복 서브레코드, 전용 UI·스크립트 문자열 등은 별도 검증이 필요합니다.

## 작업 파일

- `data/fo3/verified_assignments_all.jsonl.gz` — 최종 통합된 45,179개 고유 한국어 매핑 후보
- `data/fo3/combined_plan_report.json` — ESM 해시, 매핑 경로, 중복·검증 결과
- `data/fo3/verified_assignments.jsonl.gz` — 기존 직접 매핑 검증본
- `data/fo3/direct_formid_exact.jsonl.gz` — 추가 확인된 폴아웃 3 본편 번역
- `data/fo3/direct_formid_review.jsonl.gz` — 본편 자동 매핑에서 제외한 항목
- `data/fo3/review_needed.jsonl.gz` — 초기 매핑에서 제외한 항목
- `data/fo3/unmatched_sst.jsonl.gz` — 초기 ID 매핑이 없었던 SST 항목
- `data/mcm/translations_ko.json` — MCM 한국어 번역 데이터
- `work/fo3/Data/MCM/Config/Fallout34/config.json` — MCM UI 문구 42개 번역본(동작 설정값 불변)

## 다시 검사

```powershell
python tools/build_fo3_translation_catalog.py
python tools/build_verified_plan.py
python tools/audit_missing_mapping.py
python tools/probe_fo3_direct_ids.py
python tools/probe_dlc_missing_ids.py
python tools/merge_verified_plans.py
python tools/build_mcm.py
```

## 다음 단계

1. Fallout34 설치가 최종 완료되면 ESM SHA256을 재확인하고, 현재 생성물과 비교.
2. FO4 호환 xEdit 기반 ESP 생성기(또는 검증된 동등 구현)를 작성. 원본 `Fallout34.esm`은 보존.
3. `INFO` 다중 응답, 현지화 STRINGS 키, 마스터·로드 순서, 압축 레코드, 글꼴/한국어 화면 출력을 검증.
4. 플러그인 적용 결과와 검수 제외 항목을 보고하는 릴리스 전 QA를 실행.

## 2026-11-06 FO3 누락 문자열 검사

- `verified_assignments_all.jsonl.gz`: 레코드/필드/영문 일치에 따른 기존 고유 번역 후보 45,179개. **아직 한국어 ESP/STRINGS 미생성**.
- `outstanding_translation_audit.json`: 원본 SST 사전 6개에 존재하나 자동 반영에서 제외된 6,232행(원문-대상 구조 변경 및 제거 포함).
- `field_migration_audit.json`: 위 제외 항목 중 다른 필드에 동일 영문이 존재하는 749행(터미널 중심). 수동 검토 후 필드 변경 대응 가능.
- `record_type_migration_report.json`: 레코드 종류 변경 405행 중 401행에서 동일 필드·영문 확인. 변환 대상 레코드의 의미 검토 필요.
- `unmatched_display_text_audit.json`: 알려진 37개 레코드·필드 종류의 ESM 영문 출현 66,760회 중 21,326회는 기존 번역표에 직접 연결되지 않음. 이 수치는 중복·내부 문자열·폴아웃 4 기존 문구를 포함하는 **검토 후보 수**이며 확정 게임 미번역 개수가 아님.
- `sst_reuse_audit.json`: 직접 매핑 누락 21,326회 중 SST 기반 한국어 재사용 가능성 8,781회, 동일 영문 없는 후보 12,159회, FO4 기본 플러그인 359회, 동문이역 충돌 27회. **동일 영문이라는 이유만으로 자동 적용하지 말 것**.
- `potential_sst_reuse_*.jsonl.gz`: 번역 재활용 후보 분리. `unmatched_field_entries.jsonl.gz`는 후속 검수용 전체 기록.
- `StreetLights.esm`, `DCInteriors_ComboEdition.esm`, `Interior Lighting.esp`의 이름에 대응되는 사전 파일은 이 SST 6개에 포함되어 있지 않음. 별도 모드 번역 자료 조사 필요.

기존 6,232행 검수 제외와 ESM 직접 스캔 21,326회는 **관찰 기준이 달라 단순 합산하면 안 됩니다.** 일부는 서로 겹칩니다.
## 폴아웃 3 원본 ESM 6종 직접 역검색 — 누락 원인 정정

앞선 분석에서 Fallout34의 미연결 영문 21,326회가 모두 추가 문구일 가능성을 과대평가함. 원본 Fallout3.esm 및 DLC 5종의 실제 ESM 레코드를 전수 역검색한 결과:
- 원본 ESM 6개에서 동일 영문 발견: **19,149회** (약 89.8%). 단, 사용 맥락 동일성까지 입증된 것은 아님.
- 원본 6개에서 동일 영문 미발견: **2,177회**. 추가 모드·변환기 자체 문구·FO4 텍스트 가능성 분리 필요.
- 원본과 레코드 타입·문자열 필드까지 동일한 영문: 6,113회.
- 원본과 레코드 타입은 같으나 필드가 다름: 3,820회.
- 다른 타입의 원본 레코드에서 영문 발견: 9,216회.

특히 변환 후 `INFO/NAM1`에는 원본 `DIAL/FULL`과 `INFO/RNAM`이 재배치됨. 문자열 출처의 레코드 종류/필드 변경을 고려하는 번역 재연결이 필요함.

원본 ESM 위치와 기존 FO3·DLC 한국어 SST 6종 교차 분석:
- 원본 위치 유일·타입/필드 일치·한국어 유일: 160회 (우선 검수할 강력한 후보)
- 원본 복수 위치에서 한국어 일치: 2,063회
- 다른 필드나 타입에 원본 한국어: 6,260회
- 동일 영문만으로 한국어 하나 확인: 302회
- 번역이 서로 다른 충돌: 27회
- 사용한 SST 6종에서 대응 한국어 미발견: 10,337회

관련 보고서: `generated_original_source_audit.json`, `original_translation_recovery_report.json` 및 원본 연결 후보 JSONL.GZ.
재현 스크립트: `audit_against_original_fo3.py`, `audit_generated_strings_vs_sources.py`, `audit_original_translation_links.py`.

수치는 중복을 포함한 **문자열 출현 횟수**임. 게임 내 실제 미번역 표시 횟수나 고유 문자열 수가 아니며 원본 한국어의 문맥·응답 인덱스 검수 전 자동 적용하지 않음. ESP/STRINGS 출력 미생성.
