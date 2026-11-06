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
