# Fallout34 한국어 패처 — 2026-11-06 현황

> **개발 중**: 번역 적용 후보와 MCM 출력은 준비됐지만, FO4용 한국어 ESP/STRINGS 생성과 실제 플레이 검증은 아직 하지 않았습니다.

## 한국어 대응 레코드

| 구분 | FO3 및 DLC | FNV 및 DLC |
|---|---:|---:|
| 기존 SST 번역과 ESM 텍스트 직접 일치, 필드 위치 확인 | 45,028 | 49,530 |
| 변환된 레코드 종류·문자열 필드에서 원문 일치 복구 | 1,007 | 2,765 |
| 기존 원본과 변환기 출처 연결을 통해 복구 | 2,208 | 31,191 |
| QA 후 저장한 **번역 적용 후보 출현** | **48,241** | **83,480** |
| 중복 문구 위치 모호하여 제외 | 151 | 258 |

합계 **131,721개**는 고유 문장 수가 아니라 `target FormID + 레코드 종류 + 필드 + 필드 안 인덱스`에 대응한 번역 후보 출현 수입니다. 동일 문장이 여러 레코드에 들어가면 여러 건입니다. 아직 ESP에 적용한 수가 아닙니다.

## 파일

- `data/fo3/indexed_patch_plan_candidates.jsonl.gz` — FO3 최종 통합 후보
- `data/fnv/indexed_patch_plan_candidates.jsonl.gz` — FNV 최종 통합 후보
- 두 게임 `indexed_plan_report.json` — 각 단계의 원본 ESM SHA256, 매핑 근거, QA 예외
- `data/fnv/converter_formid_map.tsv.gz` — FNV 변환기 FormID 매핑 전체 482,533행 스냅샷
- `data/fnv/converter_origin_keys_selected.tsv.gz` — FNV 생성 레코드 원본 출처 125,243행(이번 미연결 후보 대상)
- `data/fnv/converter_snapshot_manifest.json` — 원본 TSV 두 파일의 SHA256 및 압축 결과
- `work/common/Data/MCM/Config/Fallout34/config.json` — FO3와 FNV 공용 MCM 한국어 출력. UI 문구 42개, 동작 구조 보존.
- `data/mcm/shared_mcm_report.json` — 원본 양쪽 MCM 일치 및 결과 SHA 확인

## 누락 분석과 조치

폴아웃 3는 원본 ESM 6개 전체와 이전 사전을 직접 비교했습니다. 영문 미연결 21,326회 중 원본 6개에 영문이 있는 것은 19,149회입니다. 이 중 기존 한국어가 있고 원본 필드·문장과 변환 후 대상 필드가 안전하게 대응되는 2,208개를 추가 후보로 구성했습니다. 텍스트 중복 및 원본 위치가 불분명한 나머지는 별도 검토 목록으로 유지합니다.

뉴베가스는 원본 SST 10개 86,339건을 가져오고, 생성 ESM을 대조했습니다. 특히 `formid_keys.tsv`의 `INFO|dlg|<원본 플러그인>:<원본ID>` 같은 생성 키를 분석해 변환 후 `INFO/RNAM` 대사 등을 원본 번역에 재연결했습니다. 31,313개 출처 일치 후보 가운데 변수·태그 QA를 통과한 31,191개를 사용하고 122개는 보류했습니다. 최종 통합 과정에서 기존 직접 매핑 258개는 동일 원문이 한 필드에 중복되어 인덱스를 특정할 수 없어 제외했고, 추가 3개는 변수·태그 차이로 보류했습니다.

FNV 원본 TSV가 설치 종료 후 삭제되더라도 해당 버전 스냅샷으로 다시 분석할 수 있도록, 전체 ID 매핑과 필요한 원본 출처 생성 키만 압축 보관했습니다. **원본 ESM, ESP, BSA, BA2, 실행 파일은 GitHub에 수록하지 않습니다.**

## ESM 기준 버전

- FO3 `Fallout34.esm` SHA256: `be0e7f25d0a28c672de2c12afbbf402bff0bb202037c231930d4649afd138603`
- FNV `FalloutNV34.esm` SHA256: `caa2d4649c99bfcdd36e8a489f865e55f5ee9fc6087469ba0d1de2e410318897`
- **원본 ESM이 달라지면 현재 번역 목록을 그대로 적용하지 말고 재검증해야 합니다.**

## 이어서 할 일

1. FO4용 독립 ESP 번역 출력기를 작성해 마스터 목록과 레코드 구조를 검증합니다. 원본 ESM 수정은 금지합니다.
2. `INFO` 응답·선택지의 순서와 실제 인게임 표시를 검증합니다. 이번 검사도 정적 ESM/SST 매핑이므로 실제 대사 출력은 아직 확인하지 않았습니다.
3. FNV에서 원본 SST와 매칭되지 않은 생성 대사 및 별도 모드 원문을 우선 추가 검사합니다.
4. ESM 해시 검증, 설치 경로 자동 검색, 사용자 설정 백업과 재실행 QA를 패처에 통합합니다.

## 다시 실행할 주요 단계

```powershell
python tools/build_fnv_catalog.py
python tools/verify_fnv_catalog.py
python tools/verify_converted_field_migrations.py fnv
python tools/scan_fnv_unlinked_text.py
python tools/match_fnv_generated_provenance.py
python tools/qa_fnv_provenance.py
python tools/build_indexed_patch_plan.py fnv
python tools/build_indexed_patch_plan.py fo3
python tools/verify_shared_mcm.py
```

각 단계는 게임의 원본 파일을 읽기만 하며, 패처용 자료는 저장소 `data/`와 `work/`에 생성합니다.

## 번역 누락을 기준으로 다시 분석한 결과 — 2026-11-06

이전의 QA 통과 숫자가 아니라 **현재 패처 번역 목록에서 빠져 있고, 화면 출력에 사용될 수 있는 레코드 필드**를 대상으로 ESM 전체를 읽기 전용으로 스캔함. 실행 경로·게임 내 표시 여부는 별도 플레이테스트가 필요함.

- `data/fo3/visible_residual_candidates.jsonl.gz` / `data/fnv/visible_residual_candidates.jsonl.gz` — 번역 계획에서 빠진 화면 문구 후보 원본
- `data/fo3/visible_translation_backlog.csv` / `data/fnv/visible_translation_backlog.csv` — 새 번역이 필요하거나 다른 사전 검색이 필요한 P0/P1 레코드와 FormID
- `DISPLAY_GAPS.md` — 대사, 터미널, 퀘스트 등 화면 요소별 실제 후보 예시 및 미수록 고유 문자열 수

| 구분 | FO3 | 뉴베가스 |
|---|---:|---:|
| 기존 인덱스 번역 후보 | 48,241 | 83,480 |
| 새로 확인한 생성 UI / 원본 ID / 등급 접두어 직접 복구 후보 | +20,301 | +78,315 |
| 원래 사전에 한국어가 있으나 출처 문맥 확인 후 적용할 후보 | 35,697 | 52,739 |
| 현재 자료에서 추가 번역이 필요하거나 별도 출처 확인이 필요한 출현 | 8,571 | 6,831 |
| 그 마지막 항목을 레코드 타입·필드·영문별로 중복 제거 | 6,704 | 5,176 |
| P0/P1 화면 표시 우선순위의 고유 타입·필드·영문 | 5,385 | 4,252 |
| FO4 기본 게임 레코드로 분리한 영문 출현 | 355 | 358 |

**주의:** 맨 아래 누락 후보는 인게임에서 실제 출력되는 미번역 문장이라고 확정할 수 없음. 같은 원문이 필드마다 있으면 별도 계산하며, 스크립트/외부 UI 텍스트는 이 검사 범위 밖임. 또한 기존 한국어가 확인된 88,436회(두 게임 합계) 역시 아직 본 패처에 적용되지 않았으므로 별도 문맥 검수 대상으로 반드시 처리해야 함.

### 확정적인 누락 과다 집계의 원인

- FO3 `INFO/RNAM`의 `More...`가 20,300회, FNV에서 70,587회 반복됐음. 실제로는 하나의 공통 UI 문구를 생성 레코드에 복제한 것으로, `더 보기...` 대응을 동일 문자열 전체에 적용하는 후보를 생성함.
- FNV SST 대사의 원문에는 `{Curious Beep}`처럼 편집/연기 지시가 앞에 붙는데 변환 ESM에는 제거돼 있어 실제 대사 본문이 같아도 매칭하지 못한 현상 발견. 원본 ID와 실제 필드·영문을 다시 확인한 후보는 3,814회.
- 변환 과정에서 `[Small Guns 60]`, `[Speech <Global=...>%]` 등 기술 판정 접두어가 새로 붙음. 원본 ID가 확인되고 한국어 문장 및 표시 변수가 유지되는 FNV 2,736회는 새 후보에 반영. FO3 1,728회는 자동 생성한 한국어 문구가 있지만 원본 ID 연결이 부족해 문맥 검수 목록으로 분리함.
- FNV 퍽 `Lord Death (1)`처럼 기존 한국어 이름에 등급 번호를 붙인 생성 문자열 1,178회도 기존 SST 번역과 함께 검증해 후보에 넣음.

### 남은 주요 화면 표시 후보

| 화면 필드 | FO3 남은 출현 | 뉴베가스 남은 출현 |
|---|---:|---:|
| `INFO/RNAM` 대사 선택지 | 40 | 993 |
| `INFO/NAM1` 대사/자막 | 375 | 3,688 |
| `TERM/UNAM` 터미널 본문 | 974 | 112 |
| `MESG/DESC` 팝업 안내 | 550 | 65 |

현재 개발 중인 파일 `indexed_patch_plan_v2_strict_extra.jsonl.gz`는 **추가 번역 대상 지시 목록**이며 ESP/STRINGS 바이너리가 아님. 새로 추가된 FO3 20,301건 / FNV 78,315건은 실제 ESM에서 FormID, 레코드 종류, 필드 위치, 영문이 정확히 일치하는지 독립 검사해 **모두 통과**함. 그러나 인게임 출력, 종속성, 대사 연결과 로드 순서는 여전히 검증되지 않음.

다음 작업 우선순위는 번역 데이터가 없는 P0/P1 화면 필드 → 기존 SST에서 유일 한국어를 찾았지만 출처 ID가 불충분한 재연결 후보 → UI/스크립트 외부 문자열 → 실제 게임 내 표시 경로와 ESP 검증임.

## xTranslator 정의 기반 ESM 재검사

최신 [XTRANSLATOR_AUDIT.md](XTRANSLATOR_AUDIT.md)를 확인하세요. 기존의 11,880건은 수동 선정 필드만 분석한 임시 수치로, xTranslator 번역 대상 필드 전체 기준 최종 누락량이 아닙니다. 원본 ESM은 수정하지 않았습니다.

## 2026-11-06 설치 완료된 Fallout34 ESM 두 개 전용 검사

**사용자 지정 범위:** 설치된 `C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm`(FO3 및 DLC), `FalloutNV34.esm`(FNV 및 DLC) **2개만 번역**합니다. Fallout34용 ESL 7개(`Fallout34_2~4.esl`, `FalloutNV34_2~5.esl`)는 모두 151바이트이며 실제 레코드가 없는 아카이브 연결용입니다. **`F34Online.esp`, 온라인 스크립트, XDI, Fallout 4 기본 플러그인은 제외하고 수정하지 않습니다.**

관련 BA2 아카이브 20개는 총 약 65.2GB이며 모델·텍스처·음성·립싱크·스크립트가 들어 있습니다. 목록에 별도의 `.strings`/`.swf` 번역 대상은 관찰되지 않았으나, 런타임 스크립트에서 생성되는 화면 문구까지 검증한 것은 아닙니다.

### 원본 ESM 보존형 로컬 복사본

| 게임 | 기존 적용계획 | 이번 출처 검증 복구 | ESM 복사본에 실제 적용한 필드 |
|---|---:|---:|---:|
| FO3 + DLC | 68,542 | 6 | **68,548** |
| FNV + DLC | 161,795 | 729 | **162,524** |
| **합계** | **230,337** | **735** | **231,072** |

- 원본 ESM·한국어 SST·변환 ESM의 원문/타입/필드/위치/FormID를 비교했습니다. 복구 후보 중 원본이 입증됐더라도 런타임 표시 용도가 불확실한 `QUST/NNAM` 18개는 자동 적용에서 보류했습니다.
- FNV 신규 729개: `TERM/ITXT` 148개, `TERM/RNAM` 325개, `INFO/NAM1` 238개, `MESG/ITXT` 6개, `QUST/CNAM` 12개. FO3 신규 6개: `TERM/ITXT`.
- 미리보기 ESM: `work/fo3/localized_v2/Data/Fallout34.esm`, `work/fnv/localized_v2/Data/FalloutNV34.esm`. **설치 경로 원본 ESM은 전혀 교체하지 않았으며 이 로컬 ESM 바이너리는 GitHub에 포함하지 않습니다.**
- `verify_localized_esm_copy.py`의 독립 비교에서 FO3 **1,244,191**개 레코드, FNV **994,482**개 레코드의 구조 및 모든 계획된 변경 문자열을 확인했고, 계획 밖 레코드/서브레코드 바이트는 동일함을 검증했습니다. GRUP 크기, 압축 레코드 복원, UTF-8 문자열, 필드 인덱스 검사도 통과했습니다.
- **정적 검증 통과이지 인게임 완역이나 퀘스트·UI 정상 실행 확인이 아닙니다.** 수치는 고유 문장이 아닌 문자열 필드 *출현 횟수*입니다.

### 이번 추가 반영 이후 남은 xTranslator 미연결 출현 수

| 현재 분류 | FO3 + DLC | FNV + DLC |
|---|---:|---:|
| 패처 계획에 한국어가 연결되지 않은 출현 | **12,877** | **15,382** |
| 기존 사전에 번역은 있으나 출처/문맥 추가 검증 필요 | **35,697** | **52,351** |

**미연결 출현 = 실제 인게임 미번역 개수는 아닙니다.** FO3의 `INFO/NAM1` 공백 문자열 2,640회, FNV 6,920회가 위 미연결 수치에 포함됩니다. 내부 편집 정보·조건부 데이터·같은 문장 반복도 아직 남았습니다. 이들을 제외해 실제 표시되는 미번역을 찾는 후속 조사와 플레이 테스트가 필요합니다. 이전 수동 기준 고유 후보 11,880개와 이 출현 수를 혼동하지 마세요.

### 검증·생성 명령

```powershell
python tools/recover_fo3_xtranslator_provenance.py
python tools/recover_fo3_xtranslator_edid.py
python tools/recover_fnv_xtranslator_origin_verified.py
python tools/build_xtranslator_visible_verified_plan.py
python tools/build_localized_esm_copy.py fo3 --output work/fo3/localized_v3/Data/Fallout34.esm --extra-plan data/fo3/xtranslator_verified_visible_extra.jsonl.gz
python tools/build_localized_esm_copy.py fnv --output work/fnv/localized_v3/Data/FalloutNV34.esm --extra-plan data/fnv/xtranslator_verified_visible_extra.jsonl.gz
python tools/verify_localized_esm_copy.py fo3 --translated work/fo3/localized_v3/Data/Fallout34.esm --extra-plan data/fo3/xtranslator_verified_visible_extra.jsonl.gz
python tools/verify_localized_esm_copy.py fnv --translated work/fnv/localized_v3/Data/FalloutNV34.esm --extra-plan data/fnv/xtranslator_verified_visible_extra.jsonl.gz
python -m unittest discover -s tools -p 'test_localized_esm_copy.py' -v
```

ESM 출력 경로는 **사전에 존재하면 덮어쓰지 않습니다**. 새로운 버전 경로로 생성하세요. `data/{fo3,fnv}/localized_esm_copy*.json`에는 생성본 SHA256·독립 검증 결과가 보존됩니다. GitHub 저장소에는 코드·번역 계획·QA 보고서만 올립니다.

## **현재 최우선: 미번역 잔여량 감소 (2026-11-06 최신)**

사용자 지적에 따라 **완역 이전 ESM 사본 추가 생성·설치·릴리스는 중단**했습니다. 직전의 ESM 미리보기 기록은 과거 정적 검증 근거일 뿐, 이 프로젝트의 달성 목표가 아닙니다. 현재 작업은 원본 ESM·SST·변환 결과·변환기 출처 키와 필드 이동을 추적해 **번역 연결을 복구하고 남은 인게임 표시 문자열을 새로 번역하는 것**입니다. 온라인 `F34Online.esp`는 검사·수정 범위 밖입니다.

### 원본 번역 복구와 신규 한국어 대응 (원본 ESM을 수정하지 않은 데이터 계획)

| 구분 | FO3 + DLC | FNV + DLC |
|---|---:|---:|
| 이전 번역 계획 필드 출현 | 68,542 | 161,795 |
| 원본 ESM/SST 및 변환 출처 연결 복구 | 6 | 20,306 |
| 동일 INFO 레코드의 RNAM↔NAM1 정확한 영문 대조 후 번역 연결 | 1,022 | 18,304 |
| 화면 문구 직접 번역 (정확히 일치하는 타입/필드/문구 한정) | 254 | 243 |
| **현재 번역 계획 합계** | **69,824** | **200,648** |
| **여전히 번역 연결이 없는 필드 출현** | **47,298** | **29,609** |

**추가 복구 40,135개**는 기존 SST 번역의 정확한 출처 재연결 또는 개별 한국어 직접 번역의 *문자열 필드 출현 수*입니다. ESM에 설치 적용한 건수가 아닙니다. 변환된 `INFO/RNAM` 선택지에서 원본 `DIAL/FULL` 주제가 새 필드로 이동하면서 기존 한국어가 누락된 큰 원인을 찾아 원본 `INFO`의 실제 DIAL 부모 관계와 SST까지 추적했습니다. 또 같은 변환 `INFO` FormID 안에서 동일한 영문이 선택지/자막 양쪽에 있을 때, 검증된 한국어 하나를 다른 쪽에 다시 연결했습니다. 다른 FormID의 동일 영문을 무조건 재사용하는 방식은 금지합니다.

원본 ESM은 해시로 고정한 상태에서 `verify_current_esm_translation_plan.py`를 이용해 **전체 270,472개 번역 계획**의 대상 FormID·레코드 타입·필드 인덱스·영문 원본·변수/태그 일치를 독립 검증했습니다. FO3 69,824개, FNV 200,648개 검증 통과. 다만 이것은 **번역 계획 검증**이며, 인게임 완역/작동 보증은 아닙니다.

### 현재 미연결·미번역의 실제 검수 순서

| 기준 | FO3 + DLC | FNV + DLC |
|---|---:|---:|
| 현재 자료에서 새 번역이나 추가 출처가 필요한 출현 | 12,623 | 14,769 |
| 원문과 기존 한국어 후보가 있지만 연결 검수가 더 필요한 출현 | 34,675 | 14,840 |
| 대사·터미널·메시지·퀘스트 목표 등 **직접 화면 후보 출현** | 40,179 | 20,334 |
| 그중에서 별도 분리한 빈 문구/공백 출현(모든 필드 합계) | 2,659 | 6,922 |
| 내부 편집용일 수 있는 특수 필드/제어 필드 출현 | 2,032 | 1,665 |

※ 행마다 **서로 다른 분류축**을 사용하므로 합산하지 마세요. 공백/기호/편집용 정보는 인게임 미번역 문장으로 오인하면 안 됩니다. 화면 후보도 실제 런타임 도달 여부는 미확인입니다. 남은 원문은 `data/{fo3,fnv}/current_unlinked_display_review.csv`에 게임/레코드/필드/영문별로 모았습니다. 같은 영어가 여러 FormID에 있으면 개별 원본 맥락을 추가 확인해야 합니다.

### 누락만 계속 처리하는 명령 (ESM 출력 없음)

```powershell
python tools/recover_fnv_xtranslator_origin_verified.py
python tools/build_xtranslator_visible_verified_plan.py
python tools/build_manual_visible_translation_plan.py
python tools/recover_sibling_info_field_translation.py
python tools/report_remaining_esm_translation_gaps.py
python tools/verify_current_esm_translation_plan.py fo3
python tools/verify_current_esm_translation_plan.py fnv
```

직접 작성·검수한 공용 UI 문구는 `data/manual_visible_glossary_ko.json`에 있으며, 번역 문자열은 `data/{fo3,fnv}/manual_visible_translation_verified.jsonl.gz`로 대상별 분리합니다. 이 단락까지는 **직전 검수 체크포인트**입니다. 변환된 레코드 타입·필드 재연결을 추가한 최신 결과는 다음 단락에 있습니다.

## 원본 FO3/FNV → Fallout 4 레코드·필드 변경 검수 (2026-11-06 최신)

기존 검사는 원본/변환본의 타입과 필드가 일치해야만 번역을 연결한 경우가 있어 **미번역을 과다 집계했습니다**. 설치된 변환기의 `Data/F34/Fallout34_import.json`(원본 FormID 연결 3,309개) 및 `FalloutNV34_import.json`(4,422개)을 직접 조사했습니다. 다만 이 importer의 FormID 표는 대사·터미널 등 생성된 레코드 전체를 포괄하지 않습니다.

### 새로 확인한 레코드·필드 이동

| 원본 필드 → 변환 대상 필드 | FO3 | FNV |
|---|---:|---:|
| `INFO/RNAM → INFO/NAM1` | 1,753 | 6 |
| `DIAL/FULL → INFO/NAM1` | 591 | 1,241 |
| `DIAL/FULL → INFO/RNAM` | 0 | 1,242 |
| `NOTE/TNAM → TERM/UNAM` | 0 | 741 |
| `NOTE/FULL → TERM/FULL·ITXT` | 22 | 0 |
| 기타 필드 이동 (메시지·자막 등) | 0 | 53 |
| 변환기 FormID 정확한 출처로 별도 복구 | 2 | 0 |
| **합계** | **2,368** | **3,283** |

변환기 FormID로 직접 증명된 것은 FO3 2개입니다. 나머지 5,649개는 **원본 ESM 전체에서 40자 이상 영문이 단 하나의 원본 레코드·필드에만 존재**하고, 그 동일 출처에 연결된 SST 한국어가 한 가지임을 확인했습니다. 변환 대상 ESM의 영문 바이트·타입·필드 인덱스까지 독립 검증했으나, **FormID 직접 출처가 없어 최종 문맥 검수는 필요합니다.** 짧은 공통 문구는 이 방법으로 자동 연결하지 않습니다.

### 변환 필드 재연결을 포함한 현황

| 기준 (문자열 필드 출현 수, 고유 문장 수 아님) | FO3 + DLC | FNV + DLC |
|---|---:|---:|
| 이번 이전의 번역 계획 | 69,824 | 200,648 |
| 이번에 복구한 연결 | +2,368 | +3,283 |
| **현재 한국어 연결 계획** | **72,192** | **203,931** |
| **현재 미연결 출현** | **44,930** | **26,326** |
| 화면에 표시될 수 있는 미연결 후보 | 37,457 | 16,693 |
| 위 후보 중 아직 한국어 연결이 없는 출현 | **5,306** | **5,193** |
| 위 후보 중 기존 한국어 문맥 검수가 남은 출현 | **32,151** | **11,500** |
| 별도 분리한 FO4 원본 마스터 레코드 | 355 | 359 |
| 별도 분리한 빈칸·공백 | 2,659 | 6,922 |

**남은 화면 후보 10,499개 출현도 확정 인게임 미번역량은 아닙니다.** 같은 문장 중복, 조건부·미사용·편집용 데이터가 포함될 수 있습니다. 레코드 유형/필드/영문 기준 고유 문장 후보는 FO3 4,142, FNV 4,039개입니다. 반면 43,651개 출현은 기존 한국어 후보가 있지만 원본 문맥 연결을 더 확인해야 하므로 무시할 수 없습니다. **인게임 완역은 아직 달성하지 않았습니다.**

검사 도구와 증거는 `tools/recover_import_manifest_field_migrations.py`, `tools/recover_fo3_cross_field_text_provenance.py`, `tools/recover_fnv_unique_original_text_migration.py` 및 `data/{fo3,fnv}/current_unlinked_display_review.csv`에 저장했습니다. 이 단락은 당시 기준 276,123개 계획의 기록입니다. **아래가 최신 작업·보고 기준입니다.**

## 2026-11-06 — 완역 SST 출처 및 포팅 문자열 변환 복구 (최신)

FO3용 완역 SST는 **TTW 마스터 배열**을 사용해 뉴베가스 및 DLC를 마스터로 참조합니다. 이전의 단순 FO3 FormID 필터는 상당한 한국어 데이터를 활용하지 못했습니다. TTW FNV FormID를 FO3 ID로 오인하지 않도록 실제 FO3 원본 ESM의 영어/레코드 타입/필드를 독립 확인했습니다. 추가로 변환기가 생성한 [Speech 조건 접두부]와 원본 INFO 대사 중간에서 삭제한 {성우 연기·발음 지시문}을 확인해 정확한 문자열 변환을 역추적했습니다. 한국어는 사용자가 제공한 완역 SST에서 가져왔습니다.

| 새 연결 근거 | FO3 + DLC | FNV + DLC |
|---|---:|---:|
| 원본 ESM·SST의 동일 원문, 한국어 고유성 확인 | 15,376 | 10,268 |
| FO3의 TTW 마스터 참조 사전을 원본 FO3 ESM에 교차 대조 | 16,183 | — |
| 변환기에 추가된 스킬 조건 접두부 + 원본 한국어 복원 | 1,716 | 1,284 |
| FNV 대사에 남은 {편집 표식}을 유지하며 한국어 연결 | — | 355 |
| 원본의 대사 중간 {연기 지시문} 삭제를 정확히 재현 | — | 2,946 |
| **이번 추가 연결** | **33,275** | **14,853** |
| **최신 전체 번역 연결 계획** | **105,467** | **218,784** |

전체 324,251개 계획은 대상 ESM의 정확한 영문/레코드/필드 인덱스와 보호 변수·태그 정적 검증에 통과했습니다. 단, 출처 FormID가 직접 확인되지 않은 일부 복원은 **문자열·번역 사전 및 원본 ESM 증거로 연결한 후보**이므로 대사 화자/퀘스트 문맥과 인게임 검증은 별개입니다. ESM 복사본을 새로 만들거나 원본 게임 자산을 수정하지 않았습니다.

### 미번역 보고 기준 수정 — 공백·내부 데이터는 번역 작업에서 제외

사용자 요청에 따라 앞으로 **전체 xTranslator 미연결 필드 수를 '미번역 수'로 보고하지 않습니다.** 숫자를 보고해야 할 때는 플레이어에게 노출되는 용도를 가진 필드 중 비어 있지 않은 실문구를 먼저 추립니다. 다음 자료는 **번역·연결 검토 목록**으로만 사용합니다.

| 현재 미번역·재연결 *작업 후보 출현* | FO3 + DLC | FNV + DLC | 합계 |
|---|---:|---:|---:|
| 플레이어 표시 용도의 실문구 (공백/명백한 내부 ID 등 제외) | **5,215** | **1,687** | **6,902** |
| 그중 기존 한국어의 출처 연결을 추가로 찾아야 하는 항목 | 37 | 37 | 74 |
| 원본 한국어 재연결/번역원문 조사가 필요한 항목 | 5,178 | 1,650 | 6,828 |
| 레코드 종류·필드·영문별 서로 다른 작업 항목 | 4,107 | 1,080 | 5,187 |

기존에는 퀘스트 목표 필드 **QUST/NNAM**을 편집용으로 취급해 누락시킨 반면, 많은 디버그용 **QUST/CNAM**을 화면 표시 후보로 넣는 분류 오류도 있었습니다. 이를 수정했습니다. 예를 들어 실제 대사, 터미널 본문, 메시지, 아이템·키 이름, 퀘스트 목표는 작업 후보로 남기되, 공백/기호/폴아웃4 기본 마스터/조건부/테스트·에디터 ID/런타임 표시 근거가 부족한 필드는 번역 보고에서 제외하고 별도 QA 대상에 둡니다.

**중요:** 6,902는 *게임 화면에서 미번역으로 출력된 것이 확인된 수량*이 아닙니다. ESM 필드와 텍스트의 성격으로 추린 **우선 처리할 번역 작업 후보**입니다. 실제 표시 여부를 검증해야만 최종 미번역 확정 건수를 알 수 있습니다. 제외한 항목도 편집용으로 보인다는 이유만으로 영구 무시하는 것은 아니며, 실제 표시가 확인되면 작업 대상으로 옮깁니다.

미번역 작업에 사용할 기본 파일은 `data/fo3/current_translation_work_items.csv`, `data/fnv/current_translation_work_items.csv` 및 각각의 `current_translation_work_report.json`입니다. `current_unlinked_display_review.csv`도 이제 동일한 **실문구 작업 목록만** 담도록 변경했습니다. 기술 감사용 전체 데이터는 별도 `current_unlinked_esm_report.json`에 남겼지만, 그 전체 필드 수를 번역 미완료량으로 집계·보고하면 안 됩니다. 규칙은 `tools/translation_work_filter.py`, 재집계는 `tools/report_remaining_esm_translation_gaps.py`입니다.

전체 원본/변환 ESM 및 SST 재연결 근거는 `complete_sst_exact_migration_*`, `ttw_foreign_master_text_*`, `skill_prefix_*`, `editor_marker_*`, `inline_director_cues_*`, `original_native_remaining_screen_audit.json`에 기록했습니다. 정적 필드 검증 및 작업 목록 필터 회귀 테스트는 통과했지만 실제 게임에서의 텍스트 출력·문맥 검사는 미완료입니다.
