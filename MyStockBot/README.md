# MyStockBot

국내 주식(KOSPI/KOSDAQ) 관심종목의 시세·기술지표를 수집해 **기계적 5단계 종합 판정**을 내리고,
그 판정을 **과거 데이터로 되짚어 검증(백테스트)** 하는 개인용 웹앱입니다.

> ⚠️ 모든 판정은 기계적 참고 지표이며 투자 권유가 아닙니다. 최종 판단은 사용자 본인에게 있습니다.

## 구성 — 두 개의 실행 경로

이 저장소는 **하나의 앱이지만 두 경로로 동작**합니다. 데이터 소유 경계를 아는 것이 중요합니다.

| 경로 | 실행 주체 | 저장소 | 역할 |
|------|-----------|--------|------|
| **웹앱** | FastAPI 서버 + React PWA (상시 실행) | SQLite (`data/mystockbot.db`) | 실시간 대시보드·판정·백테스트·모의투자 |
| **일일 배치** | GitHub Actions 크론 (평일 KST 16:00) | Google Sheets | 장 마감 후 일일 스냅샷 누적 + 이메일 리포트 |

관심종목 목록은 **양방향 동기화**로 한 벌처럼 유지됩니다(아래 [관심종목 동기화](#관심종목-동기화) 참고).

## 주요 기능

### 판정 엔진
- **단기 판정**(60분봉 MACD+RSI)·**장기 판정**(일봉 MACD+RSI + PER/PBR/ROE)을
  `강력매수 / 매수 / 관망 / 매도 / 강력매도` 5단계로 산출
- **팩터별 점수 분해**: 어떤 지표가 몇 점을 기여했는지 근거를 노출 (`FactorBreakdown`)

### 검증 (차별화 기능)
- **판정 백테스트** — 과거 각 시점에 판정 로직을 재적용해 적중률·평균 선행수익률과
  "판정 따라가기 vs 단순 보유" 누적수익률을 비교.
  적중률에는 **95% 신뢰구간과 겹침 보정 독립 표본 수**를 함께 표시해 과신을 막습니다.
- **적립식 백테스트(DCA)** — "매월 N주씩 사왔다면 지금 얼마?" 시뮬레이션 (정량/정액 모드)

### 화면 (모바일 PWA 우선, 하단 3탭)
| 경로 | 화면 | 내용 |
|------|------|------|
| `/` | 메인 | 코스피·코스닥 지수, 관심종목 판정 분포, Top Movers |
| `/watchlist` | 관심종목 | 종목 검색·추가·삭제, 카드 목록, 정렬·필터, 실시간 틱 |
| `/paper` | 모의투자 | 가상 시드머니로 매수·매도, 보유 평가손익, 거래내역 |
| `/stocks/:code` | 상세 | 팩터 분해, 볼린저·RSI·MACD, 멀티 타임프레임 캔들차트, 백테스트·DCA |

### 데이터·인프라
- **실시간 틱**: KIS WebSocket(H0STCNT0) 구독 → 브라우저 WS 중계 (무수신 워치독 내장)
- **시세 소스**: KIS Open API 1차 → yfinance 폴백 (60분봉은 yfinance)
- **캔들 영속화**: SQLite `candles` 테이블에 read-through 누적 (백테스트 재료)
- **휴장일 인지**: KRX 휴장일 캘린더로 불필요한 조회·중복 기록 차단

## 기술 스택

**백엔드** Python 3.11 · FastAPI · uvicorn · APScheduler · SQLite · pandas · ta · websockets
**프론트엔드** React 18 · TypeScript · Vite · lightweight-charts · vite-plugin-pwa
**데이터** KIS Open API · yfinance · Google Sheets API (gspread)
**품질** pytest · ruff · GitHub Actions CI

## 디렉터리 구조

```
MyStockBot/
├── server/                  # FastAPI 웹앱 (상시 실행)
│   ├── main.py              #   앱 조립·lifespan(수집루프·WS·스케줄러 기동)
│   ├── auth.py              #   Bearer 토큰 미들웨어
│   ├── schemas.py           #   Pydantic 응답 계약
│   ├── routers/             #   watchlist·snapshot·stocks·indices·paper·stream
│   └── services/            #   collector(수집루프)·kis_ws·candles·backtest·dca·
│                            #   indices·paper·scheduler·snapshot_cache·timeseries
├── src/                     # 공용 모듈 + 일일 배치 경로
│   ├── main.py              #   크론 엔트리포인트(시트 기록 + 이메일)
│   ├── crawler.py           #   KIS/yfinance 시세·재무 조회
│   ├── indicators.py        #   RSI·MACD·볼린저 + 5단계 판정 로직
│   ├── kis_auth.py          #   토큰/approval_key 캐시 + 전역 rate-limit
│   ├── db.py                #   SQLite 스키마·쿼리(관심종목·캔들·모의투자)
│   ├── market_calendar.py   #   KRX 휴장일 캘린더
│   ├── watchlist_sync.py    #   관심종목 시트↔SQLite 동기화
│   ├── sheets.py            #   Google Sheets 연동
│   ├── stock_master.py      #   전 종목 마스터 다운로드·파싱(검색용)
│   ├── notifier.py          #   Gmail HTML 리포트
│   └── pipeline.py          #   배치 수집 오케스트레이션
├── web/                     # React PWA
├── tests/                   # pytest
├── scripts/                 # 수동 운영 스크립트
├── config.py                # 전역 상수·환경변수 키
├── prd.md                   # 제품 요구사항 + 구현 현황
└── DEPLOY.md                # 배포 가이드
```

## 환경변수

`.env`(로컬·서버) 또는 GitHub Secrets(크론)에 설정합니다.

| 변수 | 필요 경로 | 설명 |
|------|-----------|------|
| `KIS_APP_KEY` / `KIS_APP_SECRET` | 웹앱·크론 | KIS Open API 자격증명 |
| `KIS_ACCOUNT_NO` | (선택) | KIS 계좌번호 |
| `MYSTOCKBOT_API_TOKEN` | 웹앱 | API 인증 토큰. **미설정 시 인증 비활성** |
| `CORS_ALLOWED_ORIGINS` | 웹앱 | 허용 오리진(쉼표 구분). 기본 `http://localhost:5173` |
| `MYSTOCKBOT_DB_PATH` | 웹앱 | SQLite 경로. 기본 `data/mystockbot.db` |
| `PAPER_SEED_DEFAULT` | 웹앱 | 모의투자 초기 시드머니(원). 기본 `10000000` |
| `SPREADSHEET_ID` | 크론·동기화 | 대상 Google Sheets ID |
| `GOOGLE_CREDENTIALS_JSON` | 크론·동기화 | 서비스 계정 JSON 전체 |
| `SENDER_EMAIL` / `NOTIFY_EMAIL` / `GMAIL_APP_PASSWORD` | 크론 | Gmail 리포트 발송 (2FA 앱 비밀번호 필수) |
| `VITE_API_BASE` | 프론트 | 백엔드 공개 URL(배포 시). 개발 중에는 비워 두면 Vite 프록시 사용 |

## 로컬 실행

### 백엔드

```bash
pip install -r requirements.txt
cd MyStockBot
uvicorn server.main:app --reload      # http://localhost:8000
```

> `server.main` 의 `sys.path` 설정은 `MyStockBot/` 디렉터리에서 실행하는 것을 전제로 합니다.

### 프론트엔드

```bash
cd MyStockBot/web
npm install
npm run dev                            # http://localhost:5173
```

### Docker

```bash
cd MyStockBot
docker compose up -d --build
```

자세한 배포(홈PC + 터널, PWA 설치)는 [DEPLOY.md](./DEPLOY.md) 참고.

### 일일 배치 수동 실행

```bash
cd MyStockBot
python src/main.py            # 휴장일이면 아무것도 하지 않고 종료
FORCE_RUN=1 python src/main.py  # 휴장일에도 강제 실행(테스트용)
```

## 테스트·린트

```bash
cd MyStockBot
pytest                 # 순수 계산부·파서·동기화 규칙
ruff check .
cd web && npm run build  # tsc + vite build
```

PR·`develop`/`main` 푸시 시 GitHub Actions(`.github/workflows/ci.yml`)가 위를 모두 실행합니다.

## 관심종목 동기화

웹앱(SQLite)과 크론(Google Sheets `Dashboard` 탭)은 서로 다른 저장소를 쓰지만
`src/watchlist_sync.py` 가 두 목록을 수렴시킵니다.

| 방향 | 시점 | 동작 |
|------|------|------|
| 앱 → 시트 | 추가·삭제 즉시 | 추가 시 Dashboard 에 upsert / 삭제 시 **C열에 `해제` 표시** |
| 시트 → 앱 | 부팅 시 + 평일 매시 :50 | Dashboard 에만 있는 코드를 앱에 **추가** |

- 삭제는 시트 행을 **지우지 않습니다** — C열 표시만 남기므로 사용자가 직접 입력한 내용이
  보존되고, 셀을 비우면 되돌릴 수 있습니다.
- 시트에서 사라진 종목을 앱에서 **자동 삭제하지는 않습니다**. 시트 오독·권한 오류 한 번이
  관심종목 전체를 날리는 위험이 더 크기 때문입니다(삭제는 앱에서 수행).
- `GOOGLE_CREDENTIALS_JSON`·`SPREADSHEET_ID` 가 없으면 동기화는 **조용히 비활성**되고
  웹앱은 그대로 동작합니다.
- 즉시 수렴시키려면: `POST /api/watchlist/sync`

## 데이터 무결성 규칙 (알고 있어야 할 것)

- **시트 `날짜` 컬럼은 실행일이 아니라 거래일(`bar_date`)** 입니다. 휴장일에 크론이 돌아
  직전 거래일 종가를 받아도 그 종가의 원래 날짜로 기록되고, `(날짜, 종목코드)` 중복 스킵이
  걸려 같은 값이 여러 날짜로 쌓이지 않습니다.
- **휴장일 캘린더는 매년 갱신이 필요합니다.** `src/market_calendar.py` 의 `TABLE_MAX_YEAR`
  이후 연도는 고정 양력 공휴일만 인지하므로, 음력 연휴가 누락될 수 있습니다(위 `bar_date`
  규칙이 2차 방어선). 표 범위를 벗어나면 크론 로그에 경고가 남습니다.
- **백테스트는 기술적 판정만** 재적용합니다(재무지표 과거값 결측). 응답 `notes` 와 카드에
  이 사실과 표본 한계가 명시됩니다.
- **모의투자는 수수료·세금·슬리피지를 반영하지 않습니다.** 체결가는 수집 스냅샷의 최신
  종가이며, 장 마감 후에는 종가로 체결됩니다.

## 문제 해결

| 증상 | 원인·조치 |
|------|-----------|
| 종목코드 앞 `0` 이 사라짐 | Google Sheets A열 서식을 **일반 텍스트**로 변경 |
| `401 Unauthorized` (앱) | `MYSTOCKBOT_API_TOKEN` 과 웹앱 입력 토큰 불일치 |
| KIS `EGW00133` | 토큰 발급 rate-limit(1분당 1회). 잠시 후 재시도 — 토큰은 파일 캐시됨 |
| 실시간 배지가 초록인데 틱이 없음 | 무수신 워치독(3분)이 자동 재연결. 지속되면 KIS 자격증명·장 시간 확인 |
| 지수만 "데이터 없음" | KIS 지수 API 실패 후 yfinance 폴백까지 실패. 네트워크·프록시 확인 |
| 크론이 아무것도 안 함 | 휴장일 스킵 로그 확인. 테스트는 `FORCE_RUN=1` |
| 이메일 미수신 | Gmail 2FA + **앱 비밀번호** 사용 여부 확인 |

## 알려진 한계

현재 남아 있는 부족한 점과 로드맵은 [prd.md](./prd.md) §16~§20 에 정리되어 있습니다.
요약하면: 판정 로직이 MACD+RSI 2개 지표에 의존, 메인 대시보드의 시장 폭·투자자 매매동향
미구현, 단일 사용자·단일 토큰 구조, 판정 전환 알림 미구현, DCA 공유 카드·해외 종목 미지원.

## 라이선스

MIT
