# MO2용 통합 한국어 패처: 기술 설계

최신 사용자 문서는 [README.md](README.md), UTF-8·지형 오류의 기술 기록은 [UTF8_CONVERSION_HISTORY.md](UTF8_CONVERSION_HISTORY.md)를 참고하세요.

## 입력 및 출력

입력은 포팅기에서 생성된 `Fallout34.esm`과 `FalloutNV34.esm` **원본**입니다. 두 파일은 동일한 `Data` 폴더에 있어도 되고 개별 경로를 지정해도 됩니다.

- 사용자 인터페이스: `Install_Korean_Patch.bat` → `install_gui.py` (Tkinter)
- CLI: `tools/build_mo2_korean_mod.py`
- 독립 데이터: `data/canonical/manifest.json`, `data/canonical/*.utf8.text-fields.jsonl.gz`
- ESM 엔진: `tools/runtime_esm_writer.py`
- FO4 리소스 선택: `tools/fo4_korean_assets.py`, `assets/fo4_korean/`, `assets/fo4_korean_sources.json`

출력은 새로운 `Fallout34 Unified Korean` MO2 폴더입니다. 두 ESM은 **원본의 게임 자산을 로컬에서 복사하고 텍스트 필드만 수정한 파일**입니다. GitHub의 배포 데이터에는 ESM/BA2를 넣지 않습니다.

## 안전장치

1. 입력 폴아웃 3·뉴베가스 ESM의 전체 SHA-256을 canonical manifest와 비교합니다. 현재 확인된 버전이 아니면 **시작하지 않습니다**.
2. 각 번역 적용 위치는 FormID·record type·EditorID·field tag·subrecord occurrence로 지정합니다. 원본 필드 값은 공개되지 않는 **SHA-256으로 일치성 검증**합니다.
3. `LAND`·`CELL`·`WRLD` 등 모든 비텍스트 필드를 그대로 보존합니다. 필요 시 번역 레코드만 재압축하고 상위 GRUP 크기를 갱신합니다.
4. 모든 계획된 필드가 실제로 수정되어야 성공입니다. 그 수는 FO3 111,543개 + FNV 209,785개 = 321,328개입니다.
5. 최종 결과 ESM이 이미 독립 검증을 통과한 로컬 복구본의 SHA-256과 **완전히 일치**해야 합니다. 일치하지 않으면 출력 작업을 중단합니다.
6. 사용자 게임 `Data`, 기존 번역 모드, 저장소 내부 파일을 덮어쓰지 않습니다. 출력 디렉터리는 새로 생성되는 경로만 허용합니다.
7. FO4 한국어 리소스 565개 원본을 SHA-256으로 검사하고 중복 CC 언어 변형을 505개 출력 대상으로 정규화합니다. 한 `_ko` 변형만 존재할 때 영어 실행 환경의 `_en` 파일명으로 이동합니다. `_en`과 `_ko` 내용이 다를 때는 기존 `_en`을 유지합니다.
8. 실패하면 생성 중인 임시 출력 디렉터리를 정리하고 실제 원본 ESM은 수정하지 않습니다.

## 주의사항

- 패처는 모든 버전의 Fallout34 변환 ESM을 자동 인식해 번역하는 범용 도구가 아닙니다. 원본 포팅 빌드가 달라지면 별도의 구조 검증과 새 manifest가 필요합니다.
- 현재 자료는 **실제 사용자 PC에서 검증된 출력**을 기준으로 고정됐습니다. 향후 번역 수정 시 `data/canonical`과 결과 검증 해시를 새로 생성·재검사해야 합니다.
- SWF 폰트의 정적 전체 글리프 검증은 완료됐으나 실게임 표시 폭·줄바꿈·오버레이는 별도 확인이 필요합니다.
- 레거시 번역 데이터/검수 스크립트는 기본 브랜치에서 제거했으며 `archive/legacy-translation-work-20261108`에서 추적할 수 있습니다.
