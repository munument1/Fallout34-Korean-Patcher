# Fallout 34 Installer 0.9.102 한국어 원본 ESM 실험 수정

**시험용: 전체 설치 성공, 비영어권 문자 보존 및 인게임 안정성 미검증**

## 재현 오류

2026-11-22 공식 설치기 0.9.102에서 FO3/FNV의 plugin 변환 단계가 실패했습니다.

- FO3: f34/esm.py:27 Subrecord.zstr가 UTF-8 '중공군 장교의 검'을 CP1252로 읽다 실패(0x90). 뒤따르는 Havok 오류가 실패 창에서 위에 나타날 수 있습니다.
- FNV: 동일한 Subrecord.zstr가 UTF-8 '스위치블레이드'를 CP1252로 읽다 실패(0x9d).
- 게임 설치본의 FO3/FNV ESM·ESP에 이미 UTF-8 한국어가 적용되어 있었으며, 백업본에는 영문 이름이 남아 있었습니다.

공식 변환기는 Nuitka로 컴파일한 payload/app/f34conv.exe로 동작합니다. 나머지 payload/app/f34/*.py는 플레이스홀더입니다. 공식 GitHub에 변환기 코드가 공개되지 않아 소스 수준의 UTF-8 우선/CP1252 폴백 구현은 할 수 없습니다.

## 시험용 바이너리 수정

tools/patch_fallout34_09102_utf8.py는 **정확한 0.9.102 바이너리 SHA-256**을 검사한 다음 Nuitka 함수 상수 테이블의 다음 두 지점을 같은 길이의 유효한 UTF-8 인코딩 별칭 'utf-8 '으로 바꿔 **별도의 실행 파일**을 만듭니다.

- f34.esm.Subrecord.zstr: 소스 ESM의 텍스트를 읽는 공통 함수
- f34.ctx.zstr: 변환 결과 ESM의 텍스트를 기록하는 공통 함수 (기존 CP1252 'replace'로 인한 '?' 손실 방지)

다른 CP1252 사용 부분과 게임 파일은 수정하지 않습니다.

사용법 (저장소 루트에서 PowerShell로 실행):

    python tools/patch_fallout34_09102_utf8.py "C:\path\to\Fallout34_Installer_v0.9.102\payload\app\f34conv.exe" "D:\Codex_Trans\34\work\Fallout34-0.9.102-utf8\payload\app\f34conv.exe"

원본 설치기 폴더를 별도 복사한 경우 복사본의 payload/app/f34conv.exe만 수정본으로 대체해 시험합니다. **수정 실행 파일이나 공식 설치기 전체를 GitHub에 배포하지 마세요.**

## 한계와 검증

- 위 두 함수만 대상으로 합니다. 기존 CP1252 문자로 저장된 텍스트가 입력 디코딩 함수로 전달되면 새로운 UnicodeDecodeError가 날 수 있습니다.
- 변환기의 다른 decode/encode cp1252 호출은 남아 있으므로, 한국어가 다른 경로에서 '?'로 바뀌거나 후속 단계에서 실패할 수 있습니다.
- 먼저 --only plugin 및 --variant 명령으로 게임 설치 없이 검증하고, 새 ESM의 구조·지형·한글 출력 결과를 확인해야 합니다. 기존 FO3/FNV/FO4 원본을 덮어쓰지 마세요.
- 공식 소스를 제공받으면 Subrecord.zstr의 텍스트 전용 처리를 UTF-8 strict 우선 -> CP1252 폴백으로 바꾸고, 메타데이터 식별자 및 바이너리 레코드 처리와 분리해야 합니다.

정적 유닛 검증: python -m unittest discover -s tests -p test_patch_09102_utf8.py -v
