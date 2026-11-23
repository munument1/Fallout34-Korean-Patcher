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

### 단말기 해킹 응답란 잘림 수정

`Interface/fonts_en.swf`의 FontID 6 (`Share-TechMono`)에서 Noto로 바뀐 영문·기호가 가변폭이 되어 해킹 화면의 고정 문자 격자와 맞지 않았습니다. 교체 전에는 출력 가능한 ASCII 95자(U+0020–U+007E)의 advance가 모두 11,060(DefineFont3 단위)이었지만, 교체 후에는 `i` 5,640, `W` 17,980 등으로 달라졌습니다. 이 변화는 오른쪽 응답란 잘림의 유력한 원인입니다.

해당 95자의 모양·폭·경계를 교체 전 번들(`eb398887d836c364ad72d52e9f5b06b7097a2f79`)과 동일하게 복원했습니다. Noto 한글 11,172자, 비ASCII 글리프, FontID 7 탄약 숫자, 다른 폰트와 비폰트 태그는 바꾸지 않았습니다. 전체 폰트 재빌드 시에도 `preserve_terminal_ascii()`가 이 고정폭을 보존합니다.

원본 복원과 번들 해시 갱신을 재현하려면 전체 Git 이력이 있는 체크아웃에서 `python tools/restore_fo4_terminal_font.py`를 실행합니다. `python -m unittest discover -s tests -p test_terminal_font.py -v`로 원본 ASCII 지문·고정폭·전체 한글과 비대상 태그 보존을 검사합니다.

실제 게임 검증은 아직 필요합니다. 수정 SWF를 적용한 후 해킹에서 단어 선택, `접속 거부`/일치 수 응답, 괄호 선택, 긴 단어와 일반 단말기 한글을 확인해야 합니다. 사진과 같은 응답란이 끝까지 보이는지는 인게임에서 최종 확인해야 합니다.

### v0.1.2 탄약 숫자 잘림 수정

`Roboto Condensed`의 실제 굵은체는 **FontID 7**입니다(굵기 플래그 기준). 이 글꼴의 `0`~`9`는 교체 전 숫자 모양·문자 폭·경계로 복원했습니다. 한글 11,172자와 나머지 글리프, HUD 스크립트는 유지합니다. 사용자가 게임에서 `030` / `035` 탄약 표시의 오른쪽 잘림이 해소된 것을 확인했습니다.

재빌드 도구는 번들 원본에서 이 숫자들을 보존한 뒤 Noto 교체 결과에 다시 넣습니다. 따라서 아래 재빌드 절차로도 수정이 유지됩니다. ID 7/8의 Noto 얼굴 선택은 이번 게임 테스트와 동일하게 유지하며, 일반체·굵은체 별칭은 내부 플래그로 구분합니다.

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
