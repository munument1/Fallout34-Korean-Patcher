# Fallout34 통합 한국어 패처 — FO4 번역 포함

## 실제 포함된 리소스
GitHub 저장소 assets/fo4_korean/에는 사용자가 지정한 D:\Uh-huh ex\mods\FO4_AE_1.11.191.Kor의 Interface, Programs, Strings 총 565개 파일이 들어 있습니다. MO2 관리용 meta.ini는 제외했습니다. SHA256 인덱스는 assets/fo4_korean_sources.json입니다.

이 리소스 565개는 TMR 한국어 패처 v1.0.5에 포함된 FO4_AE_1.11.191.Kor와 바이트가 일치합니다. 실행 시 TMR ZIP이나 사용자 원본 경로가 필요하지 않습니다.

FO4 본편, 공식 DLC, CC의 문자열 테이블과 한글 폰트·인터페이스 파일을 포함합니다. CC 비-localized 플러그인 문구·런타임 문구·모든 글꼴 출력이 완역 검증됐다는 뜻은 아닙니다.

## 언어 파일 정책
FO4 영문 실행 환경은 _en 문자열 테이블을 읽습니다. 이미 _en 파일이 있으면 그것을 유지합니다. _ko 파일만 있으면 출력 때 _en 이름으로 복사합니다. _en과 _ko가 함께 있으나 서로 다르면 _en을 선택하고 내용은 검수합니다(현재 33개). 원본은 변경하지 않습니다.

565개 소스 파일에서 MO2용 FO4 실제 출력 대상은 중복 언어 변형을 제외한 505개입니다.

## 상태 확인
실제 게임 PC의 저장소 루트에서 다음 명령을 실행합니다.

    python tools/build_unified_install_output.py --inspect

번역 완료되지 않은 FO3/FNV가 있으면 ready_to_build=false로 출력되며 설치 결과물을 생성하지 않습니다.

## 최종 완역 후 MO2 출력
검증 완료된 한국어 ESM 2개가 사용자의 로컬 PC에 만들어진 뒤 다음 명령으로 묶을 수 있습니다.

    python tools/build_unified_install_output.py --game-data "C:\Games\Steam\steamapps\common\Fallout 4\Data" --fo3-translated "D:\verified\Fallout34.esm" --fnv-translated "D:\verified\FalloutNV34.esm" --output "D:\Fallout34-Korean-Output"

도구는 ESM 번역 계획과 원본 게임의 비번역 필드를 바이트/레코드 단위로 대조한 후 Output/mods/Fallout34 Unified Korean 모드 아래에 FO4 Interface/Programs/Strings와 폴아웃 3·뉴베가스 번역 ESM을 출력합니다. 완료 전에는 작동을 차단합니다.

원본 설치 Fallout4.esm, 공식 DLC/CC, Fallout34.esm, FalloutNV34.esm, F34Online.esp, BA2, 리소스 전용 ESL은 수정하지 않습니다. GitHub에 FO3/FNV 번역된 ESM을 배포하지 않습니다.

## 출처와 진행 단계
FO4 번역 리소스: 사용자 제공 FO4_AE_1.11.191.Kor. 동일 리소스 대조: https://github.com/munument1/The-Midnight-Ride-KR-Patcher

FO3·FNV: 사용자 완역 SST에서 복구한 한국어 적용 계획. 통합 CLI 출력 도구와 번역 리소스는 저장소에 추가했지만 GUI 설치기와 실게임 QA는 아직 완료되지 않았습니다.
