# xTranslator 정의 기반 ESM 한글 누락 전수 비교

## 조사 방식

xTranslator는 [MGuffin/xTranslator](https://github.com/MGuffin/xTranslator)의 공개 소스(MPL-2.0) 기반 도구입니다. 설치된 `Data/Fallout4/_recorddefs.txt`를 소스의 initrecDefList 및 islstringRecord가 문자열 필드 분류에 사용합니다.
이번 검사는 **xTranslator GUI/XML 내보내기 결과가 아니라**, 오픈소스의 필드 정의를 읽는 별도 검사기가 실제 FO4 변환 ESM을 해석한 것입니다.

대상 ESM: FO3 Fallout34.esm, FNV FalloutNV34.esm. 번역 자료: FO3+FNV 한국어 SST 16개 및 이번 패처의 인덱스 번역 목록.

## 전체 정적 조사

| 지표 | 폴아웃 3 | 뉴베가스 |
|---|---:|---:|
| 번역 정의에 해당하는 필드 출현 | 121,442 | 238,860 |
| 그중 일반 텍스트로 해독된 출현 | 117,122 | 230,257 |
| 기존 번역 계획에서 일치 | 48,241 | 83,480 |
| 추가 복구 계획에서 일치 | 20,301 | 78,315 |
| 기존 한국어는 있지만 출처 문맥 확인 필요 | 35,697 | 52,739 |
| 패처 계획에 연결되지 않은 출현 | 12,883 | 15,723 |

## 미연결 문자열을 양쪽 SST 전체와 교차 확인

| 상태 | 폴아웃 3 | 뉴베가스 |
|---|---:|---:|
| FO3·FNV 어느 사전에도 동일 영문 미발견 | 4,073 | 7,045 |
| 같은 게임의 사전에서 한국어 발견 | 1,343 | 8,367 |
| 다른 게임의 사전에서 한국어 발견 | 7,412 | 164 |
| 동일 영문에 한국어 충돌 발생 | 55 | 147 |

## 이전 수동 스캔에서 빠진 번역 대상 필드

| 레코드/필드 | FO3 미연결 | FNV 미연결 |
|---|---:|---:|
| `TERM/WNAM` | 458 | 483 |
| `TERM/RNAM` | 274 | 469 |
| `QUST/NNAM` | 45 | 37 |
| `REFR/FULL` | 44 | 1 |
| `ENCH/FULL` | 84 | 115 |
| `PERK/EPFD` | 14 | 178 |
| `HAZD/FULL` | 219 | 77 |

## 생성 파일

- `data/{fo3,fnv}/xtranslator_extraction_report.json`: 필드별 스캔과 누락 집계
- `data/{fo3,fnv}/xtranslator_residual_candidates.jsonl.gz`: 번역 목록에 없는 레코드별 영문·FormID·필드 인덱스
- `data/{fo3,fnv}/xtranslator_sst_compare_report.json`: 두 게임 SST 한국어와 재대조
- `data/{fo3,fnv}/xtranslator_sst_gap_review.csv`: 한 줄씩 검수하는 문장별 CSV (영문 개행 이스케이프)
- `tools/audit_xtranslator_esm_strings.py` / `tools/compare_xtranslator_residual_to_sst.py`: 재현 스크립트

## 숫자의 의미와 한계

1. 모든 수치는 **문자열 출현 횟수**이며 고유 화면 문장 수나 실제 인게임 미번역 수가 아닙니다.
2. 필드 정의에 포함돼도 이 게임에서 실제 화면에 사용되지 않는 필드가 있고, TERM/WNAM이나 PERK/EPFD에는 바이너리 필드가 섞여 있습니다. 문자열로 해독되지 않은 건 별도로 기록합니다.
3. xTranslator의 조건부 proc 처리, VMAD/스크립트, BSA/BA2 외부 텍스트, 실시간 게임 호출 경로까지 정확히 복제한 검사가 아닙니다.
4. 다른 사전에 동일 영어가 있어도 문맥·원본 레코드 연결이 확인되기 전에는 자동 번역으로 적용하지 않습니다.
5. xTranslator는 기존 ESP를 현지화 또는 비현지화로 전환하는 도구가 아닙니다. 실제 ESP 생성은 xEdit 등 검증된 방식으로 별도 작업해야 합니다.
6. 결과 CSV에는 원본 게임의 영어 문구가 담겨 있으므로 GitHub 저장소는 비공개로 유지해야 합니다.

## 이어서 작업

화면에 표시될 수 있는 P0 대사, 터미널, 안내문, 퀘스트 필드부터 번역 출처 재연결 및 실제 표시 경로 확인. SST에 존재하지 않는 항목은 원본 ESM·별도 사전 대조 후 수동 번역, 인게임 QA로 마무리.

