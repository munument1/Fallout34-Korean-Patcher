# Fallout34 통합 한국어 패처

**Fallout 34 (Fallout 3 + Fallout: New Vegas inside Fallout 4)**를 한국어로 플레이하기 위한 로컬 패처입니다.

사용자가 이미 보유·설치한 **정상 Fallout34.esm / FalloutNV34.esm**을 지정하면, 기존 게임 파일을 변경하지 않고 각각 한국어화한 **복사본 ESM**과 **폴아웃 4 본편·DLC·Creation Club 한국어 리소스**, **Noto Sans KR 전체 한글 폰트**를 함께 묶어 **MO2에서 바로 등록할 수 있는 모드 폴더**를 생성합니다.

## 다운로드·실행

1. [GitHub Releases](https://github.com/munument1/Fallout34-Korean-Patcher/releases)에서 **`Windows-x64.zip`** 첨부 파일을 내려받아 통째로 압축 해제합니다. **이 Windows 실행 파일 배포본은 Python 설치가 필요 없습니다.** 소스 코드 ZIP은 실행 파일 배포본과 다릅니다.
2. 압축을 푼 폴더에서 `Fallout34-Korean-Patcher.exe`를 실행합니다. **EXE만 따로 꺼내지 말고 `assets`, `data`, `_internal` 폴더와 함께 사용**합니다.
3. Fallout34 변환기에서 생성한 원본 `Fallout34.esm` **한 파일만 선택**합니다. 같은 폴더의 `FalloutNV34.esm`을 자동으로 찾습니다. 두 ESM은 같은 폴더에 있어야 합니다.
4. **처음에 비어 있는 출력 경로 칸**에서 저장할 위치를 직접 지정하고 **한국어 MO2 모드 생성**을 누릅니다. 이미 존재하는 폴더를 선택해도 괜찮습니다. 선택한 폴더 안에 `Fallout34-Korean-Output`을 새로 만들며, 이름이 이미 있으면 `Fallout34-Korean-Output (2)`처럼 번호를 붙입니다. 기존 폴더와 파일을 덮어쓰지 않습니다. 존재하지 않는 새 경로를 직접 입력한 경우 해당 이름으로 생성합니다.
   - 변환기를 업데이트한 경우 **업데이트된 Fallout34 ESM 호환 시도**를 체크하세요. 새 포팅 원본에서 기존 번역의 FormID·종류·EDID·원문 SHA-256이 일치하는 항목만 재적용합니다.
5. 결과 `Fallout34 Unified Korean` 폴더를 MO2의 `mods` 폴더에 놓거나 MO2에서 해당 폴더를 새 모드로 등록하고 활성화합니다.

Python 3.10 이상이 설치된 개발자용 **소스 코드 실행 방법**: 저장소 ZIP을 압축 해제하거나 `git clone`한 뒤 `Install_Korean_Patch.bat`를 실행합니다. 일반 사용자는 위 Windows 실행 파일 ZIP을 이용하세요. CLI의 `--output`은 기존대로 아직 존재하지 않는 새 경로만 받습니다.

이미 별도의 FO4 한글 패치 모드를 쓰고 있다면 동일한 `Interface`, `Programs`, `Strings` 파일이 중복될 수 있으므로 **통합 모드를 사용할 때 기존 FO4 한글 패치와 기존 KR 중복 ESM 모드를 비활성화하거나 우선순위를 확인**해 주세요.

CLI 사용법:

```powershell
python tools/build_mo2_korean_mod.py `
    --fo3 "C:\Games\Steam\steamapps\common\Fallout 4\Data\Fallout34.esm" `
    --output "D:\Fallout34-Korean-Output"
```

`FalloutNV34.esm`이 다른 위치에 있다면 `--fnv "D:\...\FalloutNV34.esm"`을 추가합니다. 출력 경로는 **새로 만들어질 폴더**여야 합니다. 기존 폴더를 덮어쓰지 않습니다.

**새 Fallout34 컨버터 빌드**의 원본 ESM을 사용할 때만 CLI에 `--allow-updated-esms`를 추가할 수 있습니다. 기본값은 기존처럼 SHA-256이 확인된 빌드만 허용합니다. 호환 옵션은 기존 번역 99% 이상 일치, 지형 레코드 최소 수량, 출력 GRUP 구조를 검사합니다. 새로 추가된 문구는 자동 번역하지 않고, 변경되거나 누락된 기존 텍스트는 건너뛰어 `build-report.json`에 기록합니다. `REVIEW_REQUIRED` 결과물은 인게임 검증이 필요합니다.

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
| Fallout34.esm (FO3) | `LAND` 47,507건 | 111,543건 | `be0e7f25…` |
| FalloutNV34.esm (FNV) | `LAND` 42,467건 | 209,785건 | `caa2d464…` |

**총 321,328개**의 한국어 필드를 이식합니다. 양쪽 ESM 모두 독립적인 비텍스트 바이트·GRUP·레코드 구조 검증을 통과했고, 패처 빌드의 출력 SHA-256이 이전에 사용자의 PC에서 지형이 정상 출력된 검증본과 동일하다는 것을 실제로 확인했습니다.

**중요: 기본 모드는 위 두 원본 파일의 정확한 SHA-256을 가진 포팅 빌드만 지원합니다.** 새 ESM에는 선택적 호환 모드를 쓸 수 있지만, FormID 재배치나 기존 원문 변경이 많으면 중단하고 별도 매핑 검증이 필요합니다. 이 옵션은 모든 최신 버전의 안전성을 보장하지 않습니다. 예전 약 301MB/305MB짜리 한국어 ESM을 입력으로 사용하면 안 됩니다. [업데이트된 ESM 호환 안내](UPDATED_ESM_COMPATIBILITY.md)를 참조하세요.

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
