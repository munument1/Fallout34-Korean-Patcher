# MO2용 통합 한국어 패처: 기술 설계

최신 사용자 문서는 [README.md](README.md), UTF-8·지형 오류의 기술 기록은 [UTF8_CONVERSION_HISTORY.md](UTF8_CONVERSION_HISTORY.md)를 참고하세요.

## 입력 및 출력

입력은 포팅기에서 생성된 `Fallout34.esm`과 `FalloutNV34.esm` **원본**입니다. 두 파일은 동일한 `Data` 폴더에 있어도 되고 개별 경로를 지정해도 됩니다.

- 사용자 인터페이스: `Install_Korean_Patch.bat` → `install_gui.py` (Tkinter)
- Windows 배포본: `Fallout34-Korean-Patcher.exe` (PyInstaller onedir, `assets/`·`data/`가 같은 폴더에 위치). 이 배포본은 사용자 PC의 Python 설치가 필요 없습니다.
- GUI 입력: 두 ESM의 **공통 폴더를 선택**하며, 그 안에서 `Fallout34.esm` 및 `FalloutNV34.esm`을 자동 확인합니다. 누락 시 실제 선택 경로와 누락 파일명을 알립니다. 출력 경로 기본값은 빈칸이며, 기존 폴더를 선택하면 그 안에 `Fallout34-Korean-Output` 또는 번호가 붙은 새로운 하위 폴더를 자동 생성합니다. CLI 출력 경로의 기존 폴더 거부 정책은 유지합니다.
- Windows 단독 실행본은 패처 설치 폴더와 바탕화면 등 상위 폴더, 그리고 안전한 형제 폴더 아래에 **새 결과 폴더**를 만들 수 있습니다. 패처 내부 리소스(`assets`, `data`, `_internal`, `licenses`) 및 게임 설치 디렉터리는 출력 대상으로 사용할 수 없으며, 기존 결과 파일도 덮어쓰지 않습니다.
- CLI: `tools/build_mo2_korean_mod.py`
- 독립 데이터: `data/canonical/manifest.json`, `data/canonical/*.utf8.text-fields.jsonl.gz`
- ESM 엔진: `tools/runtime_esm_writer.py`
- FO4 리소스 선택: `tools/fo4_korean_assets.py`, `assets/fo4_korean/`, `assets/fo4_korean_sources.json`

출력은 새로운 `Fallout34 Unified Korean` MO2 폴더입니다. 두 ESM은 **원본의 게임 자산을 로컬에서 복사하고 텍스트 필드만 수정한 파일**입니다. GitHub의 배포 데이터에는 ESM/BA2를 넣지 않습니다.

## 안전장치

1. GUI와 CLI 모두 입력 ESM의 버전을 자동 확인합니다. 기존에 검증한 원본은 출력 SHA-256까지 검사하며, 다른 빌드는 아래 필드별 조건과 원본 보존 검사로 처리합니다.
2. 각 번역 적용 위치는 FormID·record type·EditorID·field tag·subrecord occurrence로 지정합니다. 원본 필드 값은 **SHA-256으로 일치성 검증**합니다. 같은 문구가 여러 레코드에 등장하는 것은 정상입니다.
3. `LAND`·`CELL`·`WRLD` 등 비텍스트 필드를 보존합니다. 번역 레코드만 필요에 따라 재압축하고 상위 GRUP 크기를 갱신합니다.
4. 기존 번역 데이터는 FO3 112,490개 + FNV 221,044개입니다. 다른 빌드에서는 조건이 일치하는 필드만 번역하고 나머지는 원문으로 유지·보고합니다. 파일 해시 차이·기준 지형 개수 차이·번역 적용률 자체로 차단하지 않습니다.
5. 업데이트된 입력은 출력 GRUP/레코드 경계를 재검사하고, 입력과 출력의 레코드·그룹 수량 및 종류와 LAND 헤더·본문 SHA-256이 일치해야 합니다. 기준 빌드와의 지형 개수 차이는 보고서에 기록합니다. 구조 오류, 원본 보존 실패 또는 일치하는 번역이 전혀 없으면 중단합니다. 중복 대상도 각 레코드의 동일성·원문 조건을 따로 검사해 일치하는 항목만 번역합니다.
6. 사용자 게임 `Data`, 기존 번역 모드, 저장소 내부 파일을 덮어쓰지 않습니다. 출력 디렉터리는 새로 생성되는 경로만 허용합니다.
7. FO4 한국어 리소스 565개 원본을 SHA-256으로 검사하고 중복 CC 언어 변형을 505개 출력 대상으로 정규화합니다. 한 `_ko` 변형만 존재할 때 영어 실행 환경의 `_en` 파일명으로 이동합니다. `_en`과 `_ko` 내용이 다를 때는 기존 `_en`을 유지합니다.
8. 실패하면 생성 중인 임시 출력 디렉터리를 정리하고 실제 원본 ESM은 수정하지 않습니다.

## 주의사항

- 원본 버전은 자동 확인하지만 새 문구를 자동 번역하지는 않습니다. 레코드 ID나 원문이 바뀐 항목은 그대로 남기므로 번역 데이터를 보완해야 합니다.
- 현재 자료는 **실제 사용자 PC에서 검증된 출력**을 기준으로 고정됐습니다. 향후 번역 수정 시 `data/canonical`과 결과 검증 해시를 새로 생성·재검사해야 합니다.
- SWF 폰트의 정적 전체 글리프 검증은 완료됐으나 실게임 표시 폭·줄바꿈·오버레이는 별도 확인이 필요합니다.
- 레거시 번역 데이터/검수 스크립트는 기본 브랜치에서 제거했으며 `archive/legacy-translation-work-20261108`에서 추적할 수 있습니다.
