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
- **팩터별 점수 분해**: 어떤 지표가 몇 점을 기여했는지 근거를 노출 (`FactorBreakdown`).
  점수·설명문·임계값은 모두 **백엔드가 계산해 내려주고** 화면은 그리기만 한다
  (규칙 단일 소스: `src/decision_rules.py`)
- **'강력' 등급은 기술 지표 확증을 요구**: 재무 지표만으로는 최고/최저 등급이 나오지 않는다.
  기술 지표가 결측일 때 그것을 중립 확증으로 오독하지 않기 위함이다

### 검증 (차별화 기능)
- **판정 백테스트** — 과거 각 시점에 판정 로직을 재적용해 적중률·평균 선행수익률과
  "판정 따라가기 vs 단순 보유" 누적수익률을 비교.
  적중률에는 **95% 신뢰구간과 겹침 보정 독립 표본 수**를 함께 표시해 과신을 막습니다.
- **적립식 백테스트(DCA)** — "매월 N주씩 사왔다면 지금 얼마?" 시뮬레이션 (정량/정액 모드).
  결과를 **9:16 세로 공유 카드**(1080×1920 PNG)로 만들 수 있습니다 — 원탭 공유
  (`navigator.share`)가 되는 기기에서는 공유 시트, 아니면 이미지 저장으로 내려갑니다.
  카드의 작은 글씨(가정·한계)는 API 응답 `notes` 를 그대로 씁니다 — 화면 문구와 계산이
  갈라지지 않게 하려는 것입니다.
- **룰 평가 하네스** (오프라인 CLI) — 판정 가중치를 바꿀 **근거가 있는지** 먼저 확인한다.
  검출력(MDE)·base rate 대비 lift·점수↔수익 단조성·비교군(단순보유)을 계산하고,
  데이터가 부족하면 "판단할 근거 없음"이라고 답한다 → [아래](#룰-평가-하네스)

### 화면 (모바일 PWA 우선, 하단 4탭)
| 경로 | 화면 | 내용 |
|------|------|------|
| `/` | 메인 | 시장 상태(장전/장중/장마감/휴장 + 카운트다운), 코스피·코스닥 지수, 시장 폭(등락종목수), 관심종목 판정 분포, Top Movers |
| `/watchlist` | 관심종목 | 종목 검색·추가·삭제, 카드 목록, 정렬·필터, 실시간 틱 |
| `/paper` | 모의투자 | 가상 시드머니로 매수·매도, 보유 평가손익, 거래내역 |
| `/alerts` | 알림 진단 | 인식된 채널·발송 조건·기준선·**최근 알림 이력** + 테스트 발송(읽기 전용) |
| `/stocks/:code` | 상세 | 팩터 분해, 볼린저·RSI·MACD, 멀티 타임프레임 캔들차트, 백테스트·DCA |

### 알림
- **판정 전환 알림** — 관심종목의 판정이 바뀌면 Discord·Slack·Gmail 로 알린다(동시 가능).
  오알림을 막는 게이트가 핵심이다(판정 없음 무시·측 변화만·히스테리시스·쿨다운·
  장 시간대 한정·발송 성공 시에만 기준선 이동) → [아래](#판정-전환-알림).
  **기본 비활성**
- **일일 수집 리포트** — 크론 배치 결과를 HTML 메일로 발송(성공/실패 종목·기준일·에러 원인)

### 데이터·인프라
- **실시간 틱**: KIS WebSocket(H0STCNT0) 구독 → 브라우저 WS 중계 (무수신 워치독 내장)
- **시세 소스**: KIS Open API 1차 → yfinance 폴백 (60분봉은 yfinance)
- **캔들 영속화**: SQLite `candles` 테이블에 read-through 누적 (백테스트 재료)
- **휴장일 인지**: KRX 휴장일 캘린더로 불필요한 조회·중복 기록 차단.
  화면에도 장 운영 상태로 노출되며, 휴장·장전에는 "N월 N일 거래일 기준"을 명시해
  데이터 신선도를 오해하지 않게 한다
- **시장 폭**: 지수 조회는 KIS 현재지수 → 일자별 지수 → yfinance 3단 폴백.
  1순위 경로에서만 등락종목수가 함께 오므로, 폴백 시 시장 폭 블록은 화면에서 숨겨진다

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
│   ├── routers/             #   watchlist·snapshot·stocks·indices·market·paper·
│                            #   stream·alerts
│   └── services/            #   collector(수집루프)·kis_ws·candles·backtest·dca·
│                            #   indices·paper·scheduler·snapshot_cache·timeseries·
│                            #   rule_eval(룰 평가 하네스)·alerts(판정 전환 알림)
├── src/                     # 공용 모듈 + 일일 배치 경로
│   ├── main.py              #   크론 엔트리포인트(시트 기록 + 이메일)
│   ├── crawler.py           #   KIS/yfinance 시세·재무 조회
│   ├── decision_rules.py    #   판정 규칙 단일 소스(라벨·점수표·임계값)
│   ├── indicators.py        #   RSI·MACD·볼린저 + 5단계 판정 + 기여요인 분해
│   ├── kis_auth.py          #   토큰/approval_key 캐시 + 전역 rate-limit
│   ├── db.py                #   SQLite 스키마·쿼리(관심종목·캔들·모의투자)
│   ├── market_calendar.py   #   KRX 휴장일 캘린더
│   ├── watchlist_sync.py    #   관심종목 시트↔SQLite 동기화
│   ├── sheets.py            #   Google Sheets 연동
│   ├── stock_master.py      #   전 종목 마스터 다운로드·파싱(검색용)
│   ├── notifier.py          #   Gmail HTML 리포트·알림 발송
│   ├── alert_channels.py    #   Discord·Slack 웹훅 발송 + 마크업 방언
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
| `KIS_MINUTE_ENABLED` | 웹앱 | 60분봉을 KIS 분봉 1차로 조회. **기본 off** — [주의사항](#60분봉-데이터-소스) |
| `KIS_MINUTE_BACKFILL_DAYS` | 웹앱 | KIS 분봉 초기 백필 거래일 수. 기본 `10` |
| `KIS_HOLIDAY_MIN_REFRESH_HOURS` | 웹앱 | 휴장일 캐시 갱신 최소 간격. 기본 `20`(공식 "1일 1회" 요청 준수) |
| `KIS_HOLIDAY_LOOKAHEAD_DAYS` | 웹앱 | 휴장일 1회 조회 시 확보할 일수. 기본 `400` |
| `INDICES_CACHE_TTL_SECONDS` | 웹앱 | 지수 조회 **성공** 캐시 TTL. 기본 `60` |
| `INDICES_ERROR_RETRY_SECONDS` | 웹앱 | 지수 조회 **실패** 후 재시도 간격. 기본 `10`. 성공 TTL 보다 길게 줘도 성공 TTL 로 조여진다 |
| `INDICES_STALE_MAX_SECONDS` | 웹앱 | 조회 실패 시 직전 성공 값을 stale 로 내주는 최대 기간. 기본 `900`. 초과하면 값 대신 실패로 표시 |
| `SPREADSHEET_ID` | 크론·동기화 | 대상 Google Sheets ID |
| `GOOGLE_CREDENTIALS_JSON` | 크론·동기화 | 서비스 계정 JSON 전체 |
| `SENDER_EMAIL` / `NOTIFY_EMAIL` / `GMAIL_APP_PASSWORD` | 크론·알림 | Gmail 리포트·판정 전환 알림 발송 (2FA 앱 비밀번호 필수) |
| `DISCORD_WEBHOOK_URL` | 알림 | Discord Webhook URL. **이 URL 자체가 비밀** — [주의사항](#판정-전환-알림) |
| `SLACK_WEBHOOK_URL` | 알림 | Slack Incoming Webhook URL. **이 URL 자체가 비밀** — [주의사항](#판정-전환-알림) |
| `DECISION_ALERT_ENABLED` | 알림 | 판정 전환 알림 켜기. **기본 off** |
| `DECISION_ALERT_VIEWS` | 알림 | 감시할 판정. 허용값 `short`·`long`(대소문자·공백 무관, 콤마 구분). 기본 둘 다. 알 수 없는 값은 경고를 남기고 무시하며, 남는 값이 없으면 기본값으로 되돌린다 |
| `DECISION_ALERT_SIDE_ONLY` | 알림 | 측(매수/관망/매도)이 바뀔 때만 알림. 기본 `1` |
| `DECISION_ALERT_CONFIRM_CYCLES` | 알림 | 확정에 필요한 연속 사이클 수. 기본 `2` |
| `DECISION_ALERT_COOLDOWN_MINUTES` | 알림 | 같은 종목·종류 최소 알림 간격. 기본 `60` |
| `DECISION_ALERT_STATE_TTL_DAYS` | 알림 | 기준선 방치 허용 일수(초과 시 무음 재시딩). 기본 `7` |
| `DECISION_ALERT_MAX_ROWS` | 알림 | 한 메시지에 실을 최대 전환 수. 초과분은 **다음 사이클로 이월**(유실 아님). 기본 `30` |
| `VITE_API_BASE` | 프론트 | 백엔드 공개 URL(배포 시). 개발 중에는 비워 두면 Vite 프록시 사용 |

## 로컬 실행

### 백엔드

```bash
pip install -r requirements.txt
cd MyStockBot
python -m uvicorn server.main:app --reload     # http://localhost:8000
```

> - `uvicorn` 이 아니라 **`python -m uvicorn`** 을 씁니다. 콘솔 스크립트가 PATH 에 없는
>   환경이 흔하고, `-m` 은 그 파이썬에 설치돼 있으면 항상 동작합니다.
> - `server.main` 의 `sys.path` 설정은 **`MyStockBot/` 디렉터리에서 실행**하는 것을
>   전제로 합니다. 다른 위치에서 실행하면 `ModuleNotFoundError: No module named 'server'`.
> - 이미 8000 포트를 쓰는 서버가 있으면 `[Errno 98] Address already in use` 가 납니다.
>   `--port 8080` 으로 바꾸거나 기존 서버를 끄세요.

### 프론트엔드

```bash
cd MyStockBot/web
npm install
npm run dev                            # http://localhost:5173
```

### 한 프로세스로 (API + UI 함께) — 권장

개발 중에는 위처럼 백엔드·프런트엔드를 따로 띄우지만(Vite dev 서버가 `/api` 를 프록시),
**빌드해 두면 서버 하나가 화면까지 서빙**합니다.

```bash
cd MyStockBot
(cd web && npm install && npm run build)   # 처음 한 번
./scripts/run_local.sh                     # → http://localhost:8000
```

`run_local.sh` 를 쓰는 이유는 **실행 전 점검**입니다. 그냥 `uvicorn server.main:app` 을
치면 두 가지에서 막히는데, 둘 다 미리 알 수 있는 것입니다:

| 증상 | 원인 | 스크립트가 하는 일 |
|---|---|---|
| `uvicorn: command not found` | 콘솔 스크립트가 PATH 에 없음 | `python -m uvicorn` 으로 실행(PATH 무관) |
| `[Errno 98] Address already in use` | 이미 다른 서버가 그 포트를 쓰는 중 | 미리 감지해 `PORT=8080` 안내 후 종료 |
| 화면이 안 뜸 | `web/dist` 빌드 없음 | 빌드 방법을 알려주고 API 만 기동 |
| `ModuleNotFoundError: server` | `MyStockBot/` 밖에서 실행 | 실행 위치를 검사해 알려줌 |

다른 포트로 띄우려면 `PORT=8080 ./scripts/run_local.sh`. 스크립트를 쓰지 않으려면
`python -m uvicorn server.main:app --port 8000` 을 직접 쓰면 됩니다(`uvicorn` 대신
`python -m uvicorn`).

KIS 자격증명이 없으면 기동 로그에 한 줄만 남고 실시간 시세를 쓰지 않습니다 —
`[kis_ws] KIS 자격증명 …이 없어 실시간 시세를 사용하지 않습니다`. 종가·판정·백테스트·
모의투자는 yfinance 폴백으로 정상 동작합니다(실시간 틱은 화면 표시 전용이라 판정에
쓰이지 않습니다).

SPA 클라이언트 라우팅(`/paper` 새로고침)은 index.html 로 폴백하지만, **`/api/...` 의
404 는 404 로 남습니다** — "그 엔드포인트가 아직 없다"는 신호를 HTML 200 으로 덮지 않습니다.

### 화면 스모크 테스트 (수동)

CI 는 `tsc -b` 와 `vite build` 만 돌립니다 — 둘 다 통과해도 화면이 비거나 레이아웃이
깨질 수 있습니다(빈 화면은 컴파일 에러가 아닙니다). 실제 브라우저로 확인하는 도구입니다.

```bash
npm i -g playwright                        # 처음 한 번
./scripts/run_local.sh &                   # 서버 기동
node scripts/smoke_ui.mjs http://localhost:8000
```

4개 화면의 마운트·핵심 문구·**탭바 줄 수**·푸터 가림·콘솔 에러·테스트 발송 왕복,
그리고 **DCA 공유 카드**(9:16 비율·밝은 픽셀 비율·대체 텍스트·PNG 저장·최악 조건에서
작은 글씨 잘림)를 확인합니다. 검사 항목은 대부분 **실제로 겪은 결함**에서 나왔습니다:

- 탭을 4개로 늘렸을 때 `.tabbar` 의 `repeat(3, 1fr)` 하드코딩 때문에 2줄로 깨졌다
  (tsc·pytest 전부 통과, 스크린샷에서만 보였다).
- 공유 카드의 마지막 가정·한계 줄이 CTA 알약에 잘렸다(DOM·픽셀 검사로는 안 잡혀
  렌더한 이미지를 눈으로 봐서 발견).
- 파일명에 한글이 섞여 확장자 없는 `download` 로 저장됐다.

공유 카드 검사에는 캔들 이력이 필요합니다(없으면 그 구간만 건너뛰고 이유를 출력).
다른 종목으로 보려면 `SMOKE_STOCK_CODE=000660 node scripts/smoke_ui.mjs ...`.

CI 에는 넣지 않았습니다(브라우저 의존성이 무겁습니다).

### Docker

```bash
cd MyStockBot
docker compose up -d --build              # http://localhost:8000 — API + UI
```

이미지가 웹 UI를 함께 빌드하고 **non-root(uid 10001)** 로 실행하며, 의존성은
`requirements.lock.txt` 로 고정합니다. 호스트 uid 가 1000 이 아니면
`UID=$(id -u) GID=$(id -g) docker compose up -d --build` 로 넘기세요(바인드 마운트한
`./data` 에 쓰기 위해). 자세한 배포(홈PC + 터널, PWA 설치)는 [DEPLOY.md](./DEPLOY.md) 참고.

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

## 룰 평가 하네스

판정 가중치(MACD ±2/±1, RSI ±1, 재무 ±1씩)와 등급 임계값(단기 ±2, 장기 ±3)은 **검증된 값이
아니다** — 손으로 정한 값이다. 숫자를 고치기 전에 근거를 만드는 도구:

```bash
cd MyStockBot
python scripts/evaluate_rules.py                    # 관심종목 전체, 기준선
python scripts/evaluate_rules.py --compare-variants # 사전 가설 변형 + 비교군까지
python scripts/evaluate_rules.py --json             # 기계 판독용
```

리포트의 첫 항목이 **검출력(MDE)** 이다. `UNDERPOWERED` 로 나오면 그 데이터로는 가중치
변경의 효과를 구분할 수 없다는 뜻이고, 정직한 결론은 "근거가 없으므로 현행 값 유지"다.
개인 관심종목 규모(수십 종목 × 400봉)에서는 대개 이렇게 나온다 — 가중치 ±1 조정의 기대효과가
1~3pp 인데 검출한계가 30pp 를 넘기 때문이다.

- 이 도구는 판정 규칙을 **바꾸지 않는다.** 근거만 보여주고, 반영은 사람이
  `src/decision_rules.py` 를 고쳐서 한다.
- **재무 가중치는 검증할 수 없다** — 과거 PER/PBR/ROE 이력이 없어 재무 점수가 항상 0이다.
  재무 변형이 기준선과 동일하게 나오는 것을 "차이 없음"으로 읽으면 거짓이다.
- 변형을 여러 개 비교해 최고를 고르는 것은 그 자체로 과최적화다. 실제 채택 결정에 필요한
  장치(실험 원장·holdout 예산·best-of-K 귀무분포)는 아직 없으며, 필요한 목록은
  [prd.md §22](./prd.md) 에 적어 두었다.

## 60분봉 데이터 소스

단기 판정에 쓰는 60분봉은 기본적으로 yfinance 에서 가져온다. 야후가 지연·결측·429 를 내면
단기 판정이 통째로 사라지므로, KIS 분봉을 1차 경로로 쓸 수 있게 구현해 두었다
(`FHKST03010230` 주식일별분봉조회 → 1분봉을 60분으로 리샘플).

**기본 비활성이다.** 켜기 전에 알아야 할 것:

- **호출량**: 1회 호출 최대 120건(1분봉)이라 하루치(390분)에 약 4회. 60분봉 MACD 에 35봉
  이상이 필요하고 하루 약 6.5봉이므로 **종목당 초기 백필에 24~32회 호출**이 든다.
  전역 스로틀이 0.5초 간격을 강제하므로 종목당 약 15초, 종목이 많으면 KIS 유량제한
  (EGW00201)에 걸릴 수 있다.
- **실호출 미검증**: 이 저장소는 KIS 자격증명 없이 개발되어 실제 응답으로 확인하지 못했다.
  필드명·페이징은 공식 예제 3곳(예제 코드·MCP 설정·공식 백테스터) 교차확인이다.

켜는 절차:

```bash
# 1) .env 에 추가
KIS_MINUTE_ENABLED=1
KIS_MINUTE_BACKFILL_DAYS=10     # 초기 백필 거래일 수(기본 10)

# 2) 서버를 띄우고 첫 수집 사이클 로그에서 스키마를 확인한다.
#    crawler 가 첫 성공 응답의 output2 키 목록을 1회 INFO 로 남긴다:
#    "[KIS] 분봉 output2 스키마(첫 응답 1회만): ['acml_tr_pbmn', 'cntg_vol', ...]"
#    stck_prpr / stck_oprc / stck_hgpr / stck_lwpr / cntg_vol / stck_bsop_date /
#    stck_cntg_hour 가 모두 있으면 파서가 맞다.

# 3) 스냅샷 응답의 source_60m 이 "kis" 로 바뀌었는지 확인한다.
```

실패 시에는 자동으로 yfinance 로 폴백하므로 켜서 안 되면 조용히 기존 동작으로 돌아간다.

## 판정 전환 알림

관심종목의 판정이 바뀌면 Discord·Slack·Gmail 로 알린다. **기본 비활성**
(`DECISION_ALERT_ENABLED=1` 로 켠다).

수집 루프가 이미 전 종목 판정을 주기적으로 산출하므로, 사이클마다 판정을 비교해 전환을
찾는다. 발송은 수집 스레드에서 `collector._state_lock` **밖에서** 하고, 이 경로에서 KIS 를
다시 부르지 않는다(전역 스로틀이 0.5초씩 잡아 사이클을 늘리기 때문).

### 어느 채널을 쓸까

**Discord 를 권한다** — 개인 서버를 즉시 만들 수 있어 워크스페이스 관리자 승인이나 앱 생성
절차가 없고, 멘션 차단이 **구조적으로** 된다(아래). Slack 은 이미 쓰는 워크스페이스가 있을 때
유리하다. 둘 다 켜도 되고, 이메일과도 병행된다.

두 채널 모두 **토큰이 없어** 갱신 로직이 필요 없다 — PRD 가 카카오톡 알림을 접었던
이유(토큰 갱신 부담)가 웹훅에는 아예 존재하지 않는다.

| | Discord | Slack |
|---|---|---|
| 웹훅 만들기 | 채널 설정 → 연동 → 웹훅 (앱 생성 없음) | 앱 생성 → Incoming Webhooks 활성화 → 채널 선택 |
| 본문 필드 | `content` (**최대 2000자**) | `text` |
| 성공 판정 | HTTP 200 (`?wait=true`) / 204 | HTTP 200 **AND** 본문 `ok` |
| 멘션 주입 차단 | `allowed_mentions:{"parse":[]}` — **구조적** | 이스케이프 — 텍스트 수준 |
| 굵게 문법 | `**굵게**` | `*굵게*` |

> Discord 쪽이 멘션 차단에서 더 강하다. 텍스트 이스케이프는 문자 조합으로 우회를 시도할 수
> 있지만 `allowed_mentions` 는 서버가 파싱 자체를 하지 않으므로 우회 대상이 없다.
> 그리고 `?wait=true` 를 붙이는 이유가 있다 — 공식 문서에 `wait=false` 면
> *"a message that is not saved does not return an error"* 라고 적혀 있어서, 조용히 버려진
> 메시지를 성공으로 읽으면 "발송 성공 시에만 기준선 이동" 규칙이 그 전환을 영구 유실시킨다.

### 연결 절차

```bash
# 1) 웹훅 URL 만들기 (원하는 쪽만 해도 된다)
#    Discord: 서버 → 채널 설정(⚙) → 연동 → 웹훅 → 새 웹훅 → URL 복사
#    Slack  : api.slack.com/apps → Create New App → Incoming Webhooks → 채널 선택

# 2) .env 에 추가 — 이 URL 자체가 자격증명이다. 절대 커밋하지 말 것(.env 는 gitignore 됨)
#    ★ 복사한 URL 전체를 그대로 넣는다. 아래 <> 를 지우고 붙여넣되 **앞에 아무것도 남기지
#      말 것** — 예시 접두사 뒤에 URL 을 이어 붙이면 값이 두 개가 되고, 그러면 발송이
#      비활성되면서 [discord] 경고가 뜬다(실제로 겪은 실수라 검증으로 막아 두었다).
DISCORD_WEBHOOK_URL=<Discord 에서 복사한 웹훅 URL 전체>
SLACK_WEBHOOK_URL=<Slack 에서 복사한 웹훅 URL 전체>
DECISION_ALERT_ENABLED=1

# 3) 서버를 띄우고 테스트 발송으로 채널이 살아 있는지 먼저 확인한다.
#    (이 엔드포인트는 ENABLED 플래그와 장 시간대 게이트를 우회한다)
#    MYSTOCKBOT_API_TOKEN 은 .env 안에만 있고 셸에는 없으므로 직접 읽어 쓴다.
TOKEN=$(sed -n 's/^MYSTOCKBOT_API_TOKEN=//p' .env | head -1 | tr -d '"'"'"'\r')
curl -X POST localhost:8000/api/alerts/test -H "Authorization: Bearer $TOKEN"
# → {"channels":["discord"],"results":{"discord":true},"detail":"성공: discord"}

# 4) 설정·기준선 확인
curl localhost:8000/api/alerts/config -H "Authorization: Bearer $TOKEN"
curl localhost:8000/api/alerts/state  -H "Authorization: Bearer $TOKEN"
```

#### 화면에서 먼저 확인하세요 — `/alerts`

`/alerts` 탭이 아래 세 가지를 보여줍니다. curl 없이 여기서 대부분 판별됩니다.

- **인식된 채널** — 비어 있으면 미설정이거나 **값이 검증에서 거부된** 것입니다
- **발송 조건** — 알림 켜짐 / 지금 발송 시간대 / 확정 사이클 / 재알림 간격
- **기준선** — "마지막으로 알린 판정". 오알림 진단의 출발점입니다
- **최근 알림** — **실제로 나간** 전환만 남는 append-only 이력. 쿨다운·히스테리시스로
  눌린 전환은 유실이 아니라 지연이므로(조건이 풀리면 발화) 중복으로 보이지 않고,
  테스트 발송도 남지 않습니다
- **테스트 발송 버튼** — 채널별 성공·실패와, 실패 시 볼 로그 태그를 함께 표시합니다

설정 자체는 바꿀 수 없습니다(읽기 전용). 웹훅 URL과 앱 비밀번호는 그 자체가 비밀이라
화면에서 다루지 않습니다 — `.env` 를 고치고 서버를 재시작하세요.

#### 알림이 안 갈 때

원인은 **서버를 띄운 터미널의 경고**에 찍힌다(웹훅 URL·토큰은 절대 찍히지 않는다).
`results` 의 채널명과 로그 태그가 다른 경우가 있어서, 실패 안내는 **로그 태그**로 알려준다.

| 증상 | 원인 | 조치 |
|---|---|---|
| `config` 의 `channels` 에 채널이 안 보임 | 환경변수 미설정, 또는 **값이 검증에서 거부됨** | 같은 터미널의 `[discord]`·`[slack]` 경고를 본다 |
| `[discord] … URL 이 두 개 이어붙어 있습니다` | 예시 접두사 뒤에 URL 을 이어 붙였다 | 앞쪽 접두사를 지우고 복사한 URL 하나만 남긴다 |
| `[discord] … 경로가 /api/webhooks/{id}/{token} 형태가 아닙니다` | URL 이 잘렸거나 다른 주소 | Discord 에서 URL 을 다시 복사한다 |
| `HTTP 404 / code 10015 (Unknown webhook)` | 웹훅이 삭제됨(채널 삭제 시 함께 사라진다) | 웹훅을 새로 만들어 교체한다 |
| `[notifier] 이메일 발송 실패: …` | Gmail 앱 비밀번호·계정 문제 | 앱 비밀번호를 재발급한다 |
| `URLError: … Tunnel connection failed` 등 | 그 머신에서 해당 도메인이 안 나간다 | 네트워크·프록시를 본다 |

`.env` 값이 의심되면 **서버와 같은 파서로** 확인한다(셸에 export 된 값이 있으면
python-dotenv 는 `.env` 를 덮지 않으므로, 셸 값이 조용히 이긴다):

```bash
python3 -c "
import os
from dotenv import load_dotenv; load_dotenv('.env')
v = os.environ.get('DISCORD_WEBHOOK_URL') or ''
print('길이', len(v), '/ 조각', len(v.split('/')), '(정상 7) / :// 횟수', v.count('://'))"
```

테스트 발송은 **동시 1건**으로 제한된다(이미 진행 중이면 `429`). 한 호출이 Slack 15초 +
SMTP 30초를 순차로 블로킹하는 동기 핸들러라, 제한이 없으면 동시 호출로 스레드풀이 고갈돼
다른 동기 엔드포인트(`/api/health`·`/api/watchlist` 등)까지 함께 멈춘다.

> ⚠️ **실발송 미검증.** 이 저장소는 Slack 도메인(`hooks.slack.com`·`api.slack.com`·
> `docs.slack.dev`)과 **Discord 도메인(`discord.com`·`discord.dev`)이** 이그레스 프록시에서
> **전부 403 CONNECT 로 막힌** 환경에서 개발되었다.
> 그래서 공식 문서 페이지도 열 수 없었고 실제 발송도 해보지 못했다. 규격은 각 벤더의
> **1차 소스**에서 교차 확인했다:
> - Slack — 공식 SDK 소스(`slackapi/python-slack-sdk` `webhook/internal_utils.py` → 인증
>   헤더 없음·Content-Type, `slackapi/java-slack-sdk` → 성공 = HTTP 200 + 본문 `ok`)
> - Discord — 공식 문서 저장소(`discord/discord-api-docs`
>   `developers/resources/webhook.mdx` → `content` 2000자·`wait` 파라미터·204,
>   `.../message.mdx` → `allowed_mentions` 기본값과 `{"parse":[]}`)
>
> 서버를 실제로 띄워 **요청을 시도하는 것까지는 확인했다** — 두 채널 모두 채널로 인식되고
> POST 를 보내며, 프록시 차단으로 실패할 때 그 이유를 로그에 남기고 웹훅 URL 은 새지 않는다.
> 남은 건 메시지가 실제로 도착하는지이고, 위 3번 테스트 발송이 **유일한 실검증 경로**다.

Gmail 은 크론 리포트와 같은 자격증명(`SENDER_EMAIL`/`NOTIFY_EMAIL`/`GMAIL_APP_PASSWORD`)을
쓴다. 둘 다 설정하면 두 채널로 모두 보내고, 하나라도 성공하면 발송으로 간주한다.

### 왜 게이트가 이렇게 많은가

이 기능의 실패 모드는 "알림이 안 온다"가 아니라 **"쓸모없는 알림이 계속 온다"** 다. 한 번
신뢰를 잃으면 알림을 꺼버리게 되고, 그러면 기능이 없는 것과 같다. 아래는 전부 이 저장소
코드에서 **실제로 확인한** 오알림 경로다(각각 `tests/test_alerts.py` 에 대응 테스트 있음).

| 게이트 | 막는 것 |
|--------|---------|
| 판정 없음 무시 | 수집 실패(`None`)·`데이터부족`이 매매 신호로 보이는 것. 지표 봉이 모자랄 때는 `데이터부족`이 아니라 0점=관망이 나오므로, 35번째 봉이 쌓이는 순간 가짜 '관망→매수'가 생긴다 |
| 기준선 = 마지막 **알린** 판정 (SQLite 영속) | 재시작마다 전 종목 알림 폭발 / A↔B 왕복 시 매번 알림 |
| 입력 구성 변화 시 무음 재시딩 | 재무 6시간 캐시가 뒤늦게 도착하면 장기 판정이 ±3점 통째로 이동한다(부팅 2~3사이클 뒤에 터진다). **필드별 존재 비트마스크**로 비교하므로 `per` 만 도착·소실하는 사이클도 잡는다 — 세 값은 독립적으로 ±1 점을 내고 관망 구간이 합계 0 **단일 점**이라 한 필드만으로도 측이 바뀐다(적자·미공시 종목은 `per` 만 결측인 경우가 흔하다). 출처 `kis↔yfinance` 전환도 같다 |
| 출처 센티널 무시 | 신선도 게이트로 저장소에서 서빙할 때 출처가 실제 값이 아닌 `"store"` 로 온다. 재시작 첫 사이클은 **항상** 저장소 서빙이라, 이걸 비교에 쓰면 전 종목 기준선이 리셋되어 영속화의 목적이 통째로 사라진다 → 알려진 출처(`kis`/`yfinance`)만 비교한다 |
| 측(side) 변화만 알림 | 골든크로스(+2 강력매수)는 **다음 봉에 필연적으로** 진입구간(+1 매수)으로 내려앉는다 → 골든크로스마다 두 번째 알림이 자동으로 따라온다(매도측 대칭) |
| 히스테리시스 N사이클 | 장중 마지막 봉이 미완성이라 계산이 흔들리는 것 |
| 쿨다운 | 같은 종목의 연속 알림 |
| 거래일 정규장(09:00~15:30)만 | 유휴 사이클(600초) > 60분봉 신선도(300초) 라서 **주말·야간에도** 재조회가 돈다 → 야후 실패/복구가 일요일 새벽 알림이 된다 |
| 발송 성공 시에만 기준선 이동 | 실패한 발송으로 기준선을 옮겨 그 전환이 영구 유실되는 것 |
| 한 메시지 상한을 넘긴 꼬리는 **이월** | 상한(`DECISION_ALERT_MAX_ROWS`)을 넘긴 전환까지 '알린 것'으로 기록하면, 어느 채널에도 실린 적 없는 전환이 다시는 보고되지 않는다 — 지수 급락일처럼 알림이 가장 필요한 날에만 터진다. 이제 잘린 꼬리는 다음 사이클에 이어서 발송된다 |
| Slack 본문 이스케이프 | 종목명은 시트·외부 API 에서 오는 미검증 문자열이다. `<!channel>` 은 Slack 의 실제 멘션 제어 시퀀스라 알림마다 채널 전원에게 푸시가 갈 수 있다 |

관심종목을 제거하면 기준선도 함께 삭제된다(`watchlist` 는 soft delete 라 행이 재사용되므로,
남겨두면 나중에 다시 추가할 때 그동안의 시장 움직임이 '방금 전환'으로 알려진다).

**게이트로 없앨 수 없는 한계:** 장중 판정은 아직 닫히지 않은 봉으로 계산한 값이다. 10시에
나온 '관망→매수'가 15:30에 되돌아갈 수 있다. 지표의 성질이므로 알림 본문에 그렇게 적어 보낸다.

## 데이터 무결성 규칙 (알고 있어야 할 것)

- **시트 `날짜` 컬럼은 실행일이 아니라 거래일(`bar_date`)** 입니다. 휴장일에 크론이 돌아
  직전 거래일 종가를 받아도 그 종가의 원래 날짜로 기록되고, `(날짜, 종목코드)` 중복 스킵이
  걸려 같은 값이 여러 날짜로 쌓이지 않습니다.
- **휴장일은 KIS 공식 API(`CTCA0903R`)를 1순위로 씁니다.** 결과는 SQLite `market_holidays`
  에 영속 저장되고, 공식 문서가 요청한 대로 **하루 1회만** 조회합니다
  (`KIS_HOLIDAY_MIN_REFRESH_HOURS`, 기본 20시간). 자격증명이 없거나 캐시에 없는 날짜는
  `src/market_calendar.py` 의 하드코딩 표(2026까지)로 폴백하며, 이때는 음력 연휴가
  누락될 수 있습니다(위 `bar_date` 규칙이 2차 방어선). 응답의 `calendar_source` 가
  `"kis"`인지 `"builtin"`인지로 판정 근거를 확인할 수 있습니다.
- **크론(GitHub Actions)은 휴장일 캐시를 쓰지 못합니다** — 러너가 매번 새로 클론되어 DB가
  비어 있습니다. 크론의 방어선은 하드코딩 표 + 거래일 기준 기록입니다.
- **백테스트는 기술적 판정만** 재적용합니다(재무지표 과거값 결측). 응답 `notes` 와 카드에
  이 사실과 표본 한계가 명시됩니다.
- **모의투자는 수수료·세금·슬리피지를 반영하지 않습니다.** 체결가는 수집 스냅샷의 최신
  종가이며, 장 마감 후에는 종가로 체결됩니다. 수수료가 없으므로
  `realized_pnl + unrealized_pnl == total_pnl` 이 정확히 성립합니다.
- **거래마다 체결가 출처를 기록합니다.** 거래내역의 배지로 확인하세요.
  - `장부가` — 현재 시세가 없어 **평균단가로 체결**한 매도입니다(상폐·거래정지·관심종목
    해제로 보유가 영구 고착되는 것을 막기 위한 폴백). 실제 시장가 체결이 아니고,
    체결가 == 평균단가라 그 건의 실현손익은 항상 0입니다 — 성적을 볼 때 걸러내세요.
  - `장외` — 장 시간 외 체결입니다. 실제 시장에서는 불가능합니다.
- **실현손익 기록 이전의 거래**는 `price_source`·`realized_pnl` 이 비어 있습니다(모르는
  값을 채워 넣지 않습니다). 그런 매도가 남아 있으면 계좌 요약이 그 건수를 알리고,
  실현·미실현 합이 총손익과 다를 수 있습니다.

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

현재 남아 있는 부족한 점과 로드맵은 [prd.md](./prd.md) §16~§22 에 정리되어 있습니다.
요약하면:

- **판정이 여전히 MACD+RSI 2개 지표에 의존한다.** 거래량·추세강도·변동성 미반영이고,
  볼린저밴드는 계산·표시만 하고 점수에는 들어가지 않는다. 팩터를 추가하려면 가중치를 정해야
  하는데 그 근거를 만들 데이터가 아직 부족하다(위 룰 평가 하네스 참고).
- **가중치·임계값은 미검증 상수다.** 되먹임 경로는 만들었지만 개인 규모 데이터로는 검출력이
  부족해 실제 채택 결정을 내릴 수 없다.
- 메인 대시보드 잔여 블록: 지수 스파크라인, 투자자 매매동향, 매크로 참고(환율·나스닥)
- 단일 사용자·단일 공유 토큰 구조 (다중 사용자 불가)
- **웹푸시 미구현** — 판정 전환 알림은 Slack·Gmail 로만 간다(브라우저 푸시 없음)
- **Discord·Slack 실발송 미검증** — 개발 환경에서 두 벤더 도메인이 전부 차단돼 규격은
  1차 소스(공식 문서 저장소·공식 SDK)로만 확인했다. `POST /api/alerts/test` 로 각자 확인해야 한다
- DCA 공유 카드·해외 종목 미지원, 모의투자 수수료·세금·슬리피지 미반영
- **컨테이너 이미지를 실제로 빌드해 본 적은 없다** — 개발 환경에 Docker 데몬이 없다.
  Dockerfile 의 가정(non-root 실행 + `/app/data` 만 쓰기 + 읽기전용 코드 + UI 서빙)은
  같은 레이아웃을 uid 10001 로 재현해 확인했고, 락파일은 해석이 정확히 재현되는 것까지
  확인했다. 하지만 `npm ci`·`apt tzdata`·이미지 안 `pip install` 은 미검증이다

## 라이선스

MIT
