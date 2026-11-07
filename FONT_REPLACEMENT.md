# Fallout 4 한국어 폰트 — Noto Sans KR 전체 한글 교체

## 바꾼 이유

기존 FO4 한국어 패치의 UI 파일에는 대부분의 내장 글꼴에 **한글 2,350자**만 들어 있었습니다. 그래서 문구가 정상적인 UTF-8이라도 `겍`, `힣` 같은 일부 한글이 네모 상자로 보일 수 있었습니다.

`FontConfig.txt`에 TTF 경로를 적는 것만으로는 해결되지 않습니다. **FO4 Scaleform SWF 내부에 실제 글리프 모양이 내장**되어 있기 때문입니다.

## 선택한 새 글꼴

**Noto Sans KR Regular / Bold** (Google Fonts / Adobe, **SIL Open Font License 1.1**).

- 공식 출처: <https://github.com/google/fonts/tree/main/ofl/notosanskr>
- 공식 라이선스: <https://github.com/google/fonts/blob/main/ofl/notosanskr/OFL.txt>
- 저장소에 함께 보관한 라이선스 사본: `licenses/NotoSansKR-OFL.txt`
- 사용자가 실제 게임에 넣는 것은 TTF가 아니라 **새 글리프를 내장한 SWF**입니다. 글꼴 소스 TTF 바이너리는 이 저장소에 따로 복사하지 않았습니다.

## 교체 범위와 검증

| 경로 | 새 한글 글리프가 있는 내장 폰트 ID | 사용 목적 |
|---|---|---|
| `Interface/fonts_en.swf` | 3, 6, 7, 8, 9, 10, 14 | 메인 UI, 대화, 터미널, 손글씨, 디버그 |
| `Interface/fonts_console.swf` | 1, 2 | 게임 콘솔 |
| `Programs/fonts_programs.swf` | 1, 2, 3, 4 | 게임 내 프로그램 UI |

총 **13개** 폰트 얼굴 각각에 **완성형 한글 11,172자를 전부 임베딩**했습니다. `폰트명`과 `FontID`를 보존해 기존 `FontConfig.txt`의 링크가 끊어지지 않게 했습니다. `Controller Buttons`의 두 글꼴은 변경하지 않았습니다.

검사 방법:

1. SWF(`CWS`)를 풀어 `DefineFont3` 태그(75)의 코드 테이블에서 실제 Unicode 코드 포인트를 검사합니다.
2. `AC00`~`D7A3` **11,172자** 존재 여부를 각각 검증합니다.
3. 원본과 교체본의 나머지 ActionScript/이미지/비폰트 태그 SHA256를 비교합니다.
4. FFDec는 교체된 폰트의 오래된 `DefineFontAlignZones`(73)를 정리할 수 있고, `Programs/fonts_programs.swf` 안의 폰트 의존 `DefineText`(11)를 다시 매핑할 수 있습니다. 이 두 가지 허용된 차이 이외의 비폰트 리소스 변경은 거부합니다.
5. 각 파일의 실제 SHA256 및 컴파일 결과는 `docs/FONT_REBUILD_REPORT.json`에 기록했습니다.

**주의:** 폰트 글리프의 존재, SWF 구조, 별칭, 비폰트 태그 정적 검증은 통과했지만, UI 폭, 문단 줄바꿈, 픽셀 선명도 및 실제 게임의 모든 UI 화면에서 확인한 것은 아닙니다. 폴아웃 4·3·뉴베가스 대화, 터미널, 콘솔을 각각 게임에서 검사해야 합니다.

## 재현 절차 (개발자)

1. JPEXS Free Flash Decompiler(FFDec 26.4.0) 실행 파일을 사용자 작업 공간에 별도 설치합니다. 저장소는 FFDec 바이너리를 포함하지 않습니다.
2. 공식 Noto Sans KR의 **전체 글꼴** Regular/Bold TTF를 준비합니다. `fontTools`로 U+AC00~U+D7A3 전부 존재하는지 확인합니다.
3. 아래와 같이 실행합니다.

```powershell
python tools/rebuild_fo4_fonts_ffdec.py `
    --ffdec "C:\path\to\ffdec-cli.exe" `
    --regular "C:\path\to\NotoSansKR-Regular.ttf" `
    --bold "C:\path\to\NotoSansKR-Bold.ttf" `
    --output "D:\temp\fallout34-font-test"
```

4. `FONT_REBUILD_REPORT.json`의 SWF 해시·글리프 수·보존 태그 검사 결과를 확인한 뒤에만 배포용 `assets/fo4_korean/`에 반영합니다. 작업 과정에서는 원본 UI 파일을 반드시 백업합니다.

```powershell
python tools/audit_fo4_swf_glyphs.py "assets/fo4_korean"
```

## MO2에서 폰트만 교체하는 경우

기존 `FO4_AE_1.11.191.Kor` 모드의 `Interface/fonts_en.swf`, `Interface/fonts_console.swf`, `Programs/fonts_programs.swf`를 교체하면 됩니다. 이번 통합 패처의 새 모드에는 이미 세 파일이 포함되므로 별도 교체하지 않아도 됩니다.

기존 FO4 한국어 모드와 통합 패처를 동시에 켜면 같은 SWF 경로가 충돌할 수 있습니다. 통합 패처 하나만 활성화하거나 MO2 충돌 우선순위를 의도적으로 선택하세요.
