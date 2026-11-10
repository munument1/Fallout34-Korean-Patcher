# Fallout34 통합 한국어 패처

**Fallout 34 (Fallout 3 + Fallout: New Vegas inside Fallout 4)**를 한국어로 플레이하기 위한 로컬 패처입니다.

사용자가 이미 보유·설치한 **정상 Fallout34.esm / FalloutNV34.esm**을 지정하면, 기존 게임 파일을 변경하지 않고 각각 한국어화한 **복사본 ESM**과 **폴아웃 4 본편·DLC·Creation Club 한국어 리소스**, **Noto Sans KR 전체 한글 폰트**를 함께 묶어 **MO2에서 바로 등록할 수 있는 모드 폴더**를 생성합니다.

## 설치 방법

**사전 준비:** Fallout 3, Fallout: New Vegas, Fallout 4 정품 설치 및 Fallout34 변환 완료, Mod Organizer 2(MO2) 설치

1. [Releases](https://github.com/munument1/Fallout34-Korean-Patcher/releases)에서 최신 **`Windows-x64.zip`**을 다운로드하고 압축을 해제합니다.
2. 압축을 푼 폴더에서 **`Fallout34-Korean-Patcher.exe`**를 실행합니다. (동봉된 폴더와 파일은 그대로 유지)
3. **`Fallout34.esm`**과 **`FalloutNV34.esm`**이 있는 폴더를 선택합니다. (일반적으로 `Fallout 4\Data`, 이미 한국어 패치된 ESM이 아닌 **변환 원본**)
4. 한국어 패치를 저장할 경로를 지정하고 **한국어 MO2 모드 생성** 버튼을 누릅니다.
5. 생성된 **`Fallout34 Unified Korean`** 폴더를 MO2의 `mods` 폴더에 넣고 활성화하면 완료됩니다.

### 주의사항

- 기존 Fallout 4 한국어 패치 및 중복 ESM 한국어 모드는 충돌 방지를 위해 비활성화하거나 우선순위를 확인해 주세요.
- 원본 ESM은 수정하지 않으며, 한국어가 적용된 복사본을 별도로 생성합니다.
- 일부 미번역 문구가 남아 있을 수 있습니다.

## 결과물 구조

```text
Fallout34-Korean-Output/
├── build-report.json
└── Fallout34 Unified Korean/
    ├── Fallout34.esm                 # 새로 생성한 한국어 복사본
    ├── FalloutNV34.esm               # 새로 생성한 한국어 복사본
    ├── FALLOUT34_KOREAN_README.txt
    ├── Interface/                    # FO4 한글 UI + 새 폰트 SWF
    ├── Programs/                     # 폴아웃 4 프로그램 및 한글 폰트
    └── Strings/                      # FO4 본편·공식 DLC·지원 CC 문자열
```

이 패처는 FO3/FNV **ESM 게임 자산을 저장소에 배포하지 않습니다.** 사용자가 자신의 게임에서 만든 ESM을 로컬에서 읽고, 저장소의 한국어 텍스트 데이터만 덮어쓴 별도 복사본을 만듭니다. 기존 `Data`의 ESM, BA2, ESL 및 원본 게임 폴더를 수정하지 않습니다.

## 현재 검증 범위

| 대상 | 원본 구조 보존 | 한국어 필드 이식 | 원본 SHA-256 |
|---|---:|---:|---|
| Fallout34.esm (FO3) | `LAND` 47,507건 | 112,490건 | `be0e7f25…` |
| FalloutNV34.esm (FNV) | `LAND` 42,467건 | 221,044건 | `caa2d464…` |

**총 333,534개**의 한국어 필드를 이식합니다. 기존 지형 복구 검증본에 지도 마커 이름 549개와 미번역 점검에서 확인한 11,657개 필드를 추가했습니다. 기존 번역 행, 변경 대상 이외의 레코드 및 비텍스트 필드가 그대로 보존됨을 독립 검증하고 출력 SHA-256 기준을 갱신했습니다.

### 미번역 점검 및 보완 (2026-11-10)

지도 이름 수정에 더해 FO3 719개·FNV 10,938개 필드를 추가 번역했습니다. FNV의 대화 페이지 선택지 `More...` 9,183곳, 라디오·인터컴 이름, 일부 저지능 대사와 대화 선택지, 터미널 기록, 시작 지역 선택, 기술·특성 선택·카지노 메뉴, 변경된 퍽 설명, 불러오기 도움말을 보완했습니다. 숫자 표시 서식과 컨트롤러 입력 토큰도 대조했습니다.

읽을 수 있는 이름·대사·터미널·메시지·퀘스트·퍽 등의 필드에서 남은 영문 후보는 **2,717개**입니다. 개발용 식별자·약어·의도적 암호문·음성 및 보관 노드 지시문 등이 섞여 있으므로 이 수치를 실제 미번역 개수나 완역률로 해석하지 않습니다. 추가 문맥 검토가 필요하며 완역을 보장하지 않습니다. 스크립트·BA2·이미지·음성 및 다른 모드의 문구와 인게임 전체 분기는 별도 점검 대상입니다.

추가 수량·남은 후보 유형·독립 보존 검증은 [`untranslated-audit.json`](data/canonical/untranslated-audit.json)에 기록했습니다. 이 감사 결과는 정적 파일 검사이며 실제 표시 폭과 줄바꿈은 인게임에서 확인해야 합니다.

### 외부 지역 이름 수정 (2026-11-10)

내부 셀(`CELL:FULL`)과 월드(`WRLD:FULL`) 이름만 번역하면 지도·발견 알림의 외부 지역 이름은 영문으로 남습니다. 이 이름은 별도 지도 마커의 `REFR:FULL`에 저장됩니다. FO3 228개·FNV 321개를 추가했습니다. 기존 한국어 사전에서 원문이 정확히 일치하고 번역이 유일한 546개를 복구하고, 포팅 모드 전용 버티버드 이동 지점 3개를 번역했습니다. `DC06c` 같은 개발용 식별자 42개는 그대로 보존합니다.

이미 생성한 모드에는 자동 반영되지 않으므로 수정 데이터가 포함된 패처로 다시 생성해야 합니다. 사전 해시·추가 수량·비텍스트 보존 검증은 [`map-marker-audit.json`](data/canonical/map-marker-audit.json)에 기록했습니다. 지도·발견 알림의 실제 표시는 인게임 재확인이 필요합니다.

**입력은 변환기가 생성한 포팅 원본 ESM이어야 합니다.** 이미 한국어화되거나 지형이 누락된 ESM을 복구하는 도구는 아닙니다. 업데이트된 원본에서도 동일 레코드·동일 원문만 번역하며, 새 문구나 ID가 바뀐 문구에는 새 번역 데이터가 필요합니다. 기존 검증 원본이 입력되면 최종 ESM 해시까지 추가 검증합니다. [업데이트된 ESM 호환 안내](UPDATED_ESM_COMPATIBILITY.md)를 참조하세요.

FO4 한국어 리소스는 기존에 저장소에 포함된 `FO4_AE_1.11.191.Kor` 자료를 사용하며, 최종 출력은 중복 언어 변형을 정리한 **505개** 파일입니다. 이 중 지원되는 CC의 일부 `_en`/`_ko` 충돌 33건은 `_en` 버전을 보수적으로 유지합니다. CC의 모든 비로컬라이즈 문구가 번역됐다는 뜻은 아닙니다.

## 폰트 변경

FO4의 기존 한글 SWF 폰트는 대다수가 한글 **2,350자**만 지원해 드문 글자가 네모로 출력됐습니다. **Noto Sans KR Regular/Bold**를 임베딩해 메뉴·콘솔·프로그램용 13개 내장 폰트가 **현대 한글 11,172자 전체**를 지원하게 교체했습니다. 원래 폰트 ID와 별칭은 유지했습니다.

재생성 방법, 테스트, 폰트 출처와 OFL 라이선스는 [FONT_REPLACEMENT.md](FONT_REPLACEMENT.md) 및 [licenses/NotoSansKR-OFL.txt](licenses/NotoSansKR-OFL.txt)를 참조하세요. 새 폰트의 전체 인게임 시각 검증은 별도로 필요합니다.

## 기록 및 이전 자료

- [UTF8_CONVERSION_HISTORY.md](UTF8_CONVERSION_HISTORY.md): CP1252/UTF-8 손상, 원본 대조 복구, xTranslator와 `NPC_:FULL` 바이너리 문제, 누락 지형의 원인, 최종 이식 검증
- [UNIFIED_INSTALLER.md](UNIFIED_INSTALLER.md): 파일 입력·출력 및 설치 안전장치 상세
- [UPDATED_ESM_COMPATIBILITY.md](UPDATED_ESM_COMPATIBILITY.md): 신규 변환기 ESM에 기존 번역 재사용, 검증과 검토 절차
- `data/canonical/manifest.json`: 사용자 소유 원본 ESM의 정확한 SHA-256, 번역 적용 필드 수, 출력 검증 해시
- `data/canonical/*.utf8.text-fields.jsonl.gz`: **한국어 번역문, 레코드 좌표 및 원본 필드 해시만** 포함하는 배포 데이터
- [`archive/legacy-translation-work-20261108`](https://github.com/munument1/Fallout34-Korean-Patcher/tree/archive/legacy-translation-work-20261108): 이전 번역 작업 중 생성한 검수 계획·중간 후보·기존 도구를 보관한 브랜치

## 출처와 주의

FO4 한국어 리소스는 사용자 보유의 `FO4_AE_1.11.191.Kor` 폴더와 [The Midnight Ride KR Patcher](https://github.com/munument1/The-Midnight-Ride-KR-Patcher)에 연계된 파일을 기반으로 구성했습니다. 원본 자료 기여자들의 크레딧·배포 조건을 존중해야 합니다. 폰트는 Noto Sans KR (SIL Open Font License 1.1)을 사용합니다.

게임 본편·DLC·컨버터·포팅 ESM·BA2는 포함하지 않습니다. 폴아웃 3, 뉴베가스, 폴아웃 4의 정품 설치 및 Fallout34 변환 결과가 필요합니다. 패처는 **게임 자산을 복사한 ESM 자체를 온라인에 배포하는 도구가 아닙니다.**

이번 빌드는 실사용 환경에서 지형 표시가 확인된 ESM과 바이트 일치를 검증했지만, 새 UI 글꼴로 모든 상황의 표시·줄바꿈·게임 안정성을 검증한 것은 아닙니다. 문제가 발생하면 원본 ESM 대신 **생성된 MO2 모드만 비활성화**해 되돌릴 수 있습니다.
