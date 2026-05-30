# MyStockBot

한국투자증권(KIS) Open API로 국내 주식 데이터를 자동 수집해 Google Sheets에 누적 저장하는 자동화 봇입니다.

## 개요

MyStockBot은 GitHub Actions를 통해 평일 KST 16:00에 자동으로 실행되어, 설정된 종목들의 시세 데이터와 기술적 지표를 수집한 뒤 Google Sheets에 저장합니다. 별도의 서버 운영 없이 깃허브의 무료 자동화 기능만으로 동작합니다.

## 주요 기능

- **자동 데이터 수집**: KIS API를 통한 일일 주식 데이터 수집
- **기술적 지표 계산**: RSI, MACD, 볼린저밴드 자동 계산
- **Google Sheets 연동**: 수집 데이터 자동 누적
- **HTML 이메일 알림**: 실행 결과 및 수집 현황 정기 보고
- **주말 자동 건너뜀**: 평일만 실행 (테스트 시 강제 실행 옵션 제공)

## 수집 데이터

총 20개 컬럼을 Google Sheets의 StockData 탭에 누적 저장합니다.

| 컬럼 | 설명 |
|------|------|
| 날짜 | 수집 일자 (YYYY-MM-DD) |
| 종목코드 | 6자리 종목 코드 |
| 종목명 | 종목 이름 |
| 시가, 종가, 저가, 고가 | 일일 OHLC |
| 거래량 | 거래량 |
| RSI | 상대강도지수 (14일) |
| MACD, MACD_Signal, MACD_Hist | MACD 지표 |
| BB_Upper, BB_Mid, BB_Lower | 볼린저밴드 (20일, 2σ) |
| PER, PBR, ROE | 밸류에이션 지표 |
| 매출액, 순이익 | 재무 지표 |

## 파일 구조

```
MyStockBot/
├── .github/workflows/stock_collector.yml  # GitHub Actions 자동화 스케줄
├── src/
│   ├── main.py          # 엔트리포인트 (주 실행 흐름)
│   ├── kis_auth.py      # KIS OAuth 토큰 발급 (파일 캐싱)
│   ├── crawler.py       # KIS API 데이터 수집
│   ├── indicators.py    # 기술적 지표 계산
│   ├── sheets.py        # Google Sheets API 연동
│   └── notifier.py      # Gmail HTML 이메일 알림
├── config.py            # 전역 상수 및 설정
├── requirements.txt     # Python 의존성
└── .env                 # 로컬 개발용 환경변수 (git 제외)
```

## 기술 스택

- **Python 3.11**
- **KIS Open API** (한국투자증권 실시간 주식 데이터)
- **Google Sheets API v4** (gspread)
- **GitHub Actions** (자동화 스케줄링)
- **라이브러리**: requests, gspread, google-auth, pandas, ta, python-dotenv, pytz

## Google Sheets 구조

### Dashboard 탭 (종목 등록)

- **A열**: 종목코드 (일반 텍스트 형식, 앞자리 0 보존)
- **B열**: 종목명 (KIS API 조회 결과 자동 입력)

사용자가 A열에 종목코드를 입력하면 봇이 자동으로 종목명을 조회하여 B열에 저장합니다.

### StockData 탭 (수집 데이터)

20개 컬럼으로 일일 데이터를 누적 저장. 새 행이 자동 추가됩니다.

## 환경변수 설정

### GitHub Secrets 설정

GitHub 저장소의 `Settings > Secrets and variables > Actions`에서 다음을 등록합니다:

| 변수명 | 설명 |
|--------|------|
| `GOOGLE_CREDENTIALS_JSON` | Google 서비스 계정 JSON 전체 내용 |
| `SPREADSHEET_ID` | 대상 Google Sheets ID |
| `SENDER_EMAIL` | 발신 Gmail 주소 |
| `NOTIFY_EMAIL` | 수신 이메일 주소 |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호 (2FA 활성 필수) |
| `KIS_APP_KEY` | KIS Open API APP KEY |
| `KIS_APP_SECRET` | KIS Open API APP SECRET |
| `KIS_ACCOUNT_NO` | KIS 계좌번호 (선택, 거래 기능용) |

### 로컬 .env 파일 (개발용)

프로젝트 루트에 `.env` 파일을 작성합니다. (Git에 커밋하지 않음)

```bash
GOOGLE_CREDENTIALS_JSON='{"type":"service_account","project_id":"...","...}'
SPREADSHEET_ID=YOUR_SPREADSHEET_ID
SENDER_EMAIL=your-email@gmail.com
NOTIFY_EMAIL=recipient@example.com
GMAIL_APP_PASSWORD=your_app_password
KIS_APP_KEY=YOUR_KIS_KEY
KIS_APP_SECRET=YOUR_KIS_SECRET
KIS_ACCOUNT_NO=YOUR_ACCOUNT_NUMBER
```

## 로컬 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 평일 정상 실행

```bash
python3 src/main.py
```

실행 결과:
- 성공하면 `exit(0)`
- 실패하면 `exit(1)` (GitHub Actions에서 실패 플래그)

### 3. 주말 강제 실행 (테스트용)

```bash
FORCE_RUN=1 python3 src/main.py
```

`FORCE_RUN=1`을 설정하면 주말에도 실행됩니다.

## 동작 흐름

1. **실행 조건 확인**: 평일 여부 확인 (주말이면 건너뜀)
2. **종목 목록 로드**: Dashboard 탭에서 종목코드 목록 조회
3. **데이터 수집**: KIS API로 각 종목의 OHLC, 거래량, 재무 지표 조회
4. **지표 계산**: RSI, MACD, 볼린저밴드 계산 (pandas + ta)
5. **Sheets 저장**: 수집된 데이터를 StockData 탭에 행 추가
6. **이메일 알림**: 실행 결과를 HTML 형식으로 발송

실패 시 오류 정보도 함께 알림.

## 주의사항

### Google Sheets 설정

- **Dashboard A열 서식**: 반드시 "일반 텍스트"로 설정하여 종목코드 앞 0 보존
  - 예: `005930` (삼성전자)가 `5930`으로 인식되지 않도록
- **종목 직접 입력**: A열에 입력할 때 앞에 작은따옴표 붙이기 → `'005930`

### KIS API

- **토큰 캐싱**: KIS API 토큰은 1일 1회 발급 제한 → `/tmp/kis_token_cache.json`에 자동 캐싱
- **IP 제한 금지**: GitHub Actions는 Azure 해외 IP에서 실행 → KIS 포털의 IP 접근 제한 설정 금지

### Gmail 설정

- **2FA 필수**: Gmail 2단계 인증 활성화 필수
- **앱 비밀번호**: Google 계정에서 "앱 비밀번호" 생성 후 사용 (일반 비밀번호 X)

## 실행 스케줄

GitHub Actions는 다음 일정에 자동 실행됩니다:

```yaml
cron: '0 7 * * 1-5'  # UTC 07:00, 월~금 (= KST 16:00)
```

- **UTC 07:00** = KST **16:00** (한국 장 마감 후)
- **월~금만** 실행

## 문제 해결

### 종목코드가 0으로 시작하면 인식 안 됨

→ Google Sheets에서 해당 셀을 선택 → 우클릭 → "숫자 형식" → "일반 텍스트" 변경

### KIS API 오류

- `401 Unauthorized`: 토큰 만료 또는 잘못된 APP KEY/SECRET
- `429 Too Many Requests`: API 호출 제한 초과 → 대기 후 재시도

### 이메일이 오지 않음

- GMAIL_APP_PASSWORD가 올바른지 확인
- Gmail에서 "보안 수준이 낮은 앱 허용" 설정 필요 (가능하면 2FA + 앱 비밀번호 권장)

### GitHub Actions 실행 실패

Repository → Actions 탭에서 workflow 로그 확인:
- `SPREADSHEET_ID` 환경변수 누락
- `GOOGLE_CREDENTIALS_JSON` JSON 형식 오류
- 네트워크 오류 (Google/KIS API 접근 불가)

## 라이선스

MIT

## 연락처

이 프로젝트에 대한 문제나 제안은 GitHub Issues로 보고해주세요.
