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
