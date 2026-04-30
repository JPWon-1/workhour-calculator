# 출퇴근 계산기 (Workhour Calculator)

회사 출퇴근정보 엑셀(`출퇴근정보 (N).xlsx`)을 분석해 월간 근무시간, 평균, 오늘 퇴근시각을 계산하는 데스크탑 앱.

## 다운로드 (비개발자용)

[Releases](../../releases) 페이지에서 OS에 맞는 파일을 받으세요.

| OS | 파일 | 실행 |
|---|---|---|
| Windows | `WorkhourCalculator-windows.exe` | 더블클릭 |
| macOS (M1/M2/M3) | `WorkhourCalculator-macos-arm64.zip` | 압축 풀고 `WorkhourCalculator.app` 더블클릭 |
| macOS (Intel) | `WorkhourCalculator-macos-x64.zip` | 압축 풀고 `WorkhourCalculator.app` 더블클릭 |

### 첫 실행 시 OS 보안 경고 우회

서명되지 않은 앱이라 OS가 차단합니다. 한 번만 우회하면 이후엔 정상 실행됩니다.

**Windows (SmartScreen)**
1. "Windows에서 PC를 보호했습니다" 창에서 → **추가 정보** 클릭
2. **실행** 버튼 클릭

**macOS (Gatekeeper)**
1. `WorkhourCalculator.app`을 **우클릭 → 열기**
2. "확인되지 않은 개발자..." 경고 → **열기** 클릭
3. 다음부터는 그냥 더블클릭

## 사용법

1. 회사 시스템에서 `출퇴근정보 (N).xlsx` 다운로드
2. 앱 실행 → 자동으로 다운로드 폴더의 최신 파일 인식 (수동 선택도 가능)
3. **출근시각** 입력 (HH:MM, 라운딩 자동 적용)
4. **분석 실행** 클릭
5. 상단 패널에 목표 퇴근시각 + 실시간 카운트다운 표시

## 회사 룰 (자동 반영)

- 출근: 30분 단위 올림 (08:30 이전 도착은 모두 08:30)
- 퇴근: 18:00 캡 (이후 미인정)
- 점심 1시간 차감
- 표준: 1일 8시간
- 연차/시간 인정은 시간 단위 절삭

## 개발자용

```bash
pip install -r requirements.txt
python workhour_ui.py        # GUI
python workhour.py <xlsx>     # CLI
```

릴리즈는 태그 push로 자동:
```bash
git tag v0.1.0
git push origin v0.1.0
```
