# MyStockBot 아키텍처 설계서

현행 아키텍처 (2026-07 리팩터링 완료). 이 문서는 FastAPI 웹앱 + React Vite PWA로 피벗 후의 최신 상태를 기록한다. 초기 cron 배치 스크립트 시절의 규격은 `prd.md` 참조(단, 현행과 크게 다름).

**대상 독자**: 다음 개발 세션의 에이전트, 또는 신규 기여자. 이 문서만 읽고 코드 착수 가능해야 함.

---

## 1. 한눈 요약

**MyStockBot**: 개인용(→3인: 본인+친구2) 한국주식 실시간 판정 웹앱. 장중 틱 스트림 수신 → 시세·지표 갱신 → 브라우저 리얼타임 플래시 + 30s 폴링 판정.

**스택**: FastAPI(Python 3.11, Docker) + React/Vite/TS PWA + SQLite WAL

**배포**: PC로컬 Docker(restart:unless-stopped) + Cloudflare Tunnel(무료 HTTPS) + Vercel 프론트(무료)

---

## 2. 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                        BROWSER (React PWA)                          │
│  /stocks/:code (차트+판정게이지) / (종목리스트)                       │
│  Token 검증(localStorage) / TokenBanner(401 처리)                   │
│  - useSnapshot (20s 폴링) → /api/snapshot                           │
│  - useTickStream (WS, 지수 백오프) → /ws/ticks?token=               │
│  - lightweight-charts (1m~240m/1d/1w/1M/1y, MA5/20/60/120)          │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP/HTTPS
                             │ WS/WSS
┌────────────────────────────▼────────────────────────────────────────┐
│               FastAPI 백엔드 (uvicorn, 워커=1)                       │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │  라우터:                                                       │  │
│ │  ├─ /api/snapshot (GET, 20ms) → collector 인메모리 상태 읽기   │  │
│ │  ├─ /api/stocks/search (GET) → stock_master 자동완성           │  │
│ │  ├─ /api/stocks/{code}/candles (GET) → candles read-through   │  │
│ │  ├─ /api/watchlist/* (CRUD) → DB                              │  │
│ │  └─ /ws/ticks (WS) → kis_ws 이벤트 중계 + 토큰 검증          │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│ ┌────────────────────────────────────────────────────────────────┐  │
│ │  백그라운드 프로세스:                                           │  │
│ │  ├─ Collector (스레드): 30s/600s 사이클, ThreadPoolExecutor(4) │  │
│ │  │  종목별 이재 격리, MACD/RSI/BB + 5단계 판정                │  │
│ │  ├─ KIS WebSocket: 실시간체결(H0STCNT0) 구독, 41종목 상한     │  │
│ │  ├─ APScheduler: 주간 stock_master 갱신(7일 stale)           │  │
│ │  └─ Candles fetch: 저장소 신선도 게이트 read-through         │  │
│ └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│ DB (SQLite WAL)                                                      │
│  ├─ candles (code, tf, t PK) → 영속 시계열 저장소                   │
│  ├─ watchlist → 활성 종목 목록(전역 1개 공유, 사용자 컬럼 없음)     │
│  ├─ stock_master (code PK) → KIS 공식 마스터(KOSPI 1788+KOSDAQ)   │
│  └─ bar_history (date+code UNIQUE) → 레거시 cron 일별 스냅샷      │
│     저장(현 웹앱 미사용, scripts/backfill_sqlite_from_sheets.py 전용) │
└────────────────────────────────────────────────────────────────────┘
                             │ HTTP/HTTPS
┌────────────────────────────▼────────────────────────────────────────┐
│                   외부 API 의존성                                     │
│  KIS (Korea Investment & Securities)                                │
│  ├─ REST: 기간별시세(1d/1w/1M/1y), 당일분봉(1m), 지표X             │
│  └─ WebSocket: 실시간체결(H0STCNT0)                               │
│  yfinance (폴백): 당일분봉 실패 시, 또는 야후 직접 조회            │
│  KRX 공휴일 달력: [미구현] 스케줄러 건너뜀 확인용                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. 모듈 맵

| 폴더 | 파일 | 책임 |
|------|------|------|
| `src/` | `main.py` | cron 배치(GitHub Actions, 불변 유지) — 일일 시트 + 이메일 |
| `src/` | `pipeline.py` | 배치 파이프라인(crawler.fetch_all 호출) |
| `src/` | `crawler.py` | KIS/yfinance API 호출 집합 — fetch_kis_ohlcv_paged(1d/1w/1M), fetch_kis_minutes(분봉), fetch_kis_ohlcv(1y), fetch_stock_price(종가만) |
| `src/` | `indicators.py` | 순수 함수: MACD, RSI, 볼린저밴드 + 5단계 판정(강력매수~강력매도) |
| `src/` | `stock_master.py` | KIS 종목마스터(mst 파일) 파싱 → DB 저장 |
| `src/` | `kis_auth.py` | KIS 토큰 발급(approval_key, 23h 캐시) |
| `server/` | `main.py` | FastAPI 앱 진입점, lifespan(db init, 수집/스케줄러/ws 시작), CORS+인증 미들웨어 |
| `server/auth.py` | 토큰 검증 미들웨어(MYSTOCKBOT_API_TOKEN) |
| `server/routers/` | `snapshot.py` | GET /api/snapshot → collector.get_state (2ms) |
| `server/routers/` | `stocks.py` | GET /api/stocks/search, GET /api/stocks/{code}/candles → stock_master, candles.get_candles |
| `server/routers/` | `watchlist.py` | CRUD /api/watchlist/* |
| `server/routers/` | `stream.py` | WS /ws/ticks, 토큰 검증(?token=), kis_ws 이벤트 중계 |
| `server/services/` | `collector.py` | 후술(백그라운드 수집 루프, 지표 계산, 상태 저장) |
| `server/services/` | `candles.py` | 후술(read-through 캔들 저장소, 소스 라우팅) |
| `server/services/` | `kis_ws.py` | 후술(KIS 실시간WS, 구독 관리, 리스너 큐 브로드캐스트) |
| `server/services/` | `scheduler.py` | APScheduler (평일 매일 16:00 stock_master 갱신, 7일 stale 조건) |
| `server/` | `schemas.py` | Pydantic 응답 모델 (WatchlistItemOut, SnapshotResponse, SearchResponse, CandlesResponse 등) |
| `web/` | `package.json` | React 18, Vite, PWA, lightweight-charts |
| `web/src/` | `App.tsx` | 라우팅(/, /stocks/:code), 토큰 배너 |
| `web/src/hooks/` | `useSnapshot.ts` | 20s 폴링(/api/snapshot) |
| `web/src/hooks/` | `useTickStream.ts` | WS 연결 + 지수 백오프 + visibilitychange |
| `web/src/components/` | 차트, 종목리스트, 게이지 UI |
| `config.py` | 환경변수 로드 (KIS_APP_KEY, KIS_ACCOUNT_NO, CORS_ALLOWED_ORIGINS, COLLECTOR_INTERVAL_*, TIMEZONE 등) |
| `src/` | `db.py` | SQLite 초기화 + 간단한 CRUD (watchlist, candles 읽기) |

---

## 4. 핵심 설계 결정

### 4.1 수집/제공 분리 (2026-07 리팩터링)

**왜?** 리팩터링 전: 모든 /api 라우트가 매 요청마다 외부 API(KIS/yfinance)를 호출 → 평균 응답시간 13초.

**결정**: 백그라운드 스레드 수집 루프 + 인메모리 상태 스냅샷:
- **Collector**: 종목마다 병렬(ThreadPoolExecutor 4), 신선도 게이트로 중복 요청 방지
  - 장중 30s, 장외 600s 사이클
  - 지표 계산 후 원자적으로 상태 교체(캐시 일관성)
- **Snapshot API** (/api/snapshot): 단순 읽기 → **2ms 응답**
- **Candles**: read-through 저장소(신선하면 DB, 아니면 fetch→upsert→재조회)

**트레이드오프**: 브라우저가 최신 지표를 30초 뒤에 봄 (하이브리드로 보정: 가격·등락률은 실시간 WS 틱으로 플래시, 판정은 30s 폴링).

---

### 4.2 데이터 소스 라우팅 (일·분봉 이중화)

**왜?** KIS REST/WS는 무료이나 한계가 있고(API 콜 제한, 당일분봉만 지원), yfinance는 느리고 신뢰 관계가 불명확.

**결정**:
- **1d/1w/1M**: KIS 기간별시세(FHKST03010100) 페이지네이션(100건/호출) 우선 → 실패 시 yfinance(2년/10년/max)
- **1y**: KIS 단일 호출만(폴백 없음, 설계상 필요 없음)
- **분봉(1m~60m)**: KIS 당일분봉(FHKST03010200, 페이지당 30건×15페이지 최대450분>정규장390분) 우선 → 실패/빈 데이터 시 yfinance 직접 조회
- **120m/240m**: 60m을 서버에서 리샘플

**장점**: 국내 단기(분봉~주봉) 신뢰도 높음, 폐장 후 역사 조회도 yfinance로 보완.

---

### 4.3 WebSocket 하이브리드 (틱 스트림 + 폴링 지표)

**왜?** 실시간 가격은 보여주되, 지표 번복은 피하면서 네트워크 대역 절약.

**결정**:
- **WS (/ws/ticks)**: KIS 실시간체결(H0STCNT0) → 브라우저에 **틱 플래시**(가격, 등락률만)
- **Polling (/api/snapshot)**: 20s마다 최신 지표(MACD, RSI, BB, 판정) 조회

**구현**:
- KIS WS 세션: 매니저 패턴, approval_key 23h 캐시, 지수 백오프, 전 종목 재구독
- WS 클라이언트: hidden 상태에서도 WS 연결은 유지되며, visible 복귀 시에만 끊어진 연결을 백오프 리셋 후 즉시 재연결(빠른 복귀 목적, 배터리 절약 목적 아님)

---

### 4.4 SQLite WAL + 영속 저장소 (read-through)

**왜?** 서버 재시작 후에도 차트 이력 유지, 그리고 candles 테이블에 누적.

**결정**:
- **DB**: SQLite WAL 모드(쓰기 병목 방지, 읽기 동시성 확보)
- **docker-compose**: 볼륨 마운트 `/app/data` (WSL 네이티브 ext4 필수, UNC 경로 X)
- **read-through**: 신선도 게이트(분봉 60s, 일봉+ 600s) 기준으로 캐시/fetch 판정
- **저장소 신선도**: collector.py와 candles.py가 동일 기준(`_DAILY_FRESH_SECONDS` 등) 공유

---

### 4.5 인증 2단계 (토큰 + Cloudflare Access)

**왜?** 퍼블릭 웹앱인데 누구나 watchlist 조작하면 안 됨.

**결정**:
- **1단계**: MYSTOCKBOT_API_TOKEN (openssl rand -hex 32)
  - /api/* Bearer 검증(compare_digest)
  - 예외: /api/health, OPTIONS, 토큰 미설정 시 전체 비활성
  - **함정**: WS는 헤더 제약상 ?token= 쿼리로 노출(코드 주석에 고지)
- **2단계 권장**: Cloudflare Access (이메일 3개 허용, 개별 회수 가능)
- **미들웨어 순서**: 인증을 CORS 전에 등록 → 401에도 CORS 헤더 붙음

---

### 4.6 PWA (정적 자산만 캐시, API 캐시 원천 차단)

**왜?** 앱 껍데기(정적 자산)는 캐시해 모바일에서 빠르게 뜨되, 시세는 신선도가 생명이라 API 응답은 절대 캐시하지 않는다(묵은 가격이 최신처럼 보이는 사고 방지).

**결정**:
- **정적 자산만 프리캐시** (JS, CSS, 폰트) → vite-plugin-pwa
- **API 응답 캐시 X** (서비스워커에서 /api/* 요청은 network-only)
- **스텐드얼론 설치** (주소창 없는 앱 모드, Android/iOS 지원)

---

## 5. 데이터 소스 매트릭스

| 타임프레임 | 우선순위 1 | 한계/조건 | 우선순위 2 | 추가 노트 |
|-----------|----------|---------|----------|---------|
| 1m | KIS 당일분봉 | 당일만(FHKST03010200, 페이지 15=450분) | yfinance | 수집루프 60s 게이트 |
| 5m | KIS 리샘플(1m) | 당일만 | yfinance(5m) | 리샘플 유틸 재사용 |
| 15m | KIS 리샘플(1m) | 당일만 | yfinance(15m) | - |
| 30m | KIS 리샘플(1m) | 당일만 | yfinance(30m) | - |
| 60m | KIS 리샘플(1m) | 당일만, MACD 35봉 필요(며칠 누적) | yfinance(60m) | 수집루프 600s 게이트 |
| 120m | KIS 60m 리샘플 | - | yfinance 60m 리샘플 | - |
| 240m | KIS 60m 리샘플 | - | yfinance 60m 리샘플 | - |
| 1d | KIS 기간별시세 페이지네이션 | 과거 깊이 1000까지 조회 가능 | yfinance(2y) | 폐장 후 종가 즉시 반영(2026-07 기준, 상장/폐지로 변동 가능) |
| 1w | KIS 기간별시세 페이지네이션 | 과거 깊이 1000까지 | yfinance(10y) | - |
| 1M | KIS 기간별시세 | 과거 깊이 1000까지 | yfinance(max) | - |
| 1y | KIS 기간별시세 | 폴백 없음(설계상) | 없음 | 필요 시 수동 추가 |

**폴백 로그**: yfinance 호출 시 "yfinance 폴백" 경고 출력(조용하지 않음) — 재발 방지.

---

## 6. 배포 설계 B안 (3인 공개)

### 6.1 개요

| 계층 | 방식 | 호스팅 | 비용 |
|-----|-----|--------|------|
| 백엔드 | Docker (uvicorn, 워커=1) | PC 로컬 + Cloudflare Tunnel | 0 |
| 프론트 | Vite SPA 빌드 | Vercel | 0 |
| 인증 1 | 토큰(Bearer) | - | 0 |
| 인증 2 | Cloudflare Access | Cloudflare 무료 | 0 |

### 6.2 아키텍처 그림

```
PC Docker (WSL2)           Cloudflare Tunnel          Vercel                Browser
┌──────────────────┐       (무료 HTTPS)              (무료)              (3인용)
│  uvicorn:8000    │◄─────────────────────►https://mystockbot.xxx.com◄──►Chrome/Safari
│  (FastAPI+DB)    │  cloudflared        (DNS 라우팅)                   Token 입력 UI
│ restart:unless   │
│   stopped        │
└──────────────────┘
   Docker Desktop
   (로그인 시
   자동시작 권장)
```

### 6.3 환경변수 설정

**MyStockBot/.env** (백엔드):
```
# KIS API
KIS_APP_KEY=<KIS앱키>
KIS_APP_SECRET=<KIS앱비밀>
KIS_ACCOUNT_NO=<계좌번호>

# 인증
MYSTOCKBOT_API_TOKEN=<openssl rand -hex 32 결과>

# CORS (Vercel 도메인 포함)
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://<vercel-프로젝트>.vercel.app,https://mystockbot.<도메인>

# 기타
TIMEZONE=Asia/Seoul
COLLECTOR_INTERVAL_MARKET=30  # 장중
COLLECTOR_INTERVAL_IDLE=600   # 장외
```

**web/.env.local** (프론트):
```
VITE_API_BASE=https://mystockbot.<도메인>
```

### 6.4 배포 실행 순서

**1) 백엔드 설정 + 재시작**:
```bash
cd MyStockBot
echo "MYSTOCKBOT_API_TOKEN=$(openssl rand -hex 32)" >> .env
# CORS_ALLOWED_ORIGINS 등 추가 입력
docker compose up -d --build
```

**2) Cloudflare Tunnel**:
```bash
cloudflared tunnel login
cloudflared tunnel create mystockbot
cloudflared tunnel route dns mystockbot <your-domain>
cloudflared tunnel run mystockbot
# 또는 시스템 서비스로 등록: cloudflared service install
```

**3) Vercel 배포**:
```bash
cd web
vercel env add VITE_API_BASE  # 환경변수 설정
vercel deploy --prod
```

**4) 친구 온보딩**:
- 링크 공유: `https://mystockbot.<your-domain>`
- 첫 접속 시 토큰 입력(초록 배너)
- PWA 설치: Android Chrome "앱 설치", iOS Safari "홈화면에 추가"

**5) 권장: Cloudflare Access**:
- Tunnel 설정 → Access 탭 → 정책 추가 → 이메일 3개 허용
- 개별 회수 가능(계정 만료 시)

---

## 7. 함정 모음 (재발 방지)

### 7.1 KIS 일봉 폴백 레거시

**사고**: 2024년 초 KIS 일봉 API가 잘못된 엔드포인트(inquire-daily-price)로 2년간 가동 → 데이터 전부 Yahoo 폴백으로 조달. source 필드로 추적 가능.

**교훈**: 폴백이 조용하지 않아야 (경고 로그 필수), source 필드로 거래 후추 확인.

### 7.2 SQLite WAL + WSL UNC 경로

**사고**: docker-compose에서 `volumes: - ./data:/app/data` 를 `/mnt/c/...` (UNC) 경로에서 실행 → 잠금 오류.

**교훈**: WSL 네이티브 ext4 경로(`/home/joon/...`)에서 compose 실행, 또는 WSL 볼륨 드라이브 사용.

### 7.3 tsc -b 캐시 + vite.config.js 덮어쓰기

**사고**: `tsc -b` 후 vite.config.js가 공개 폴더로 emit 됨 → vite가 구설정 .js 우선 로드.

**교훈**: tsconfig.node.json에서 outDir을 명시적으로 설정.

### 7.4 Starlette add_middleware 순서 (최외곽 = 마지막 등록)

**사고**: CORS를 먼저 등록 후 인증 추가 → 401 응답에 CORS 헤더가 안 붙음 → 브라우저에서 CORS 에러로 보임.

**교훈**: main.py 주석 참고. 인증을 먼저 `app.middleware("http")`, 그 후 `add_middleware(CORSMiddleware)`.

### 7.5 uvicorn INFO 로그 유실

**사고**: kis_ws.py의 logger.info가 콘솔에 안 나옴 → uvicorn이 앱 로거에 핸들러를 붙이지 않음.

**교훈**: main.py 부팅 시 `logging.basicConfig(level=logging.INFO)` 필수.

### 7.6 KIS WebSocket PINGPONG 에코 (ws.pong 아님)

**사고**: 초기 코드가 `ws.pong()` 메서드 호출 시도 → KIS는 이를 지원하지 않음 → 40초마다 강제 끊김.

**교훈**: KIS는 PING 프레임 수신 시 평문 텍스트 PONG을 그냥 `ws.send()` 로 echo (ws.pong() 메서드 불가). ping_interval=None 필수.

### 7.7 KIS 41종목 세션 상한

**사고**: 구독 종목이 41개를 넘으면 앞 41개만 유지, 나머지 자동 버림 → 일부 틱 누락.

**교훈**: kis_ws.py에서 경고 로그. 관심종목이 41개 초과면 로테이션 필요(아직 미구현).

### 7.8 KIS approval_key 23h 캐시

**사고**: kis_auth.get_approval_key를 매번 호출 → API 콜 낭비.

**교훈**: 23시간 in-memory 캐시. 캐시 만료 전 KIS가 키를 거절할 수도 있으므로 재발급 로직 필요(현재는 단순 캐시만).

### 7.9 Collector 신선도 게이트 부실

**사고**: 광 중 30초 사이클마다 외부 API를 계속 호출 → 비용 낭비, 레이트 제한 걸림.

**교훈**: collector.py의 `_last_source` 에서 (code, tf) 별로 마지막 fetch 타임스탬프 기록, 신선 여부 판정.

### 7.10 2026-07-17 KRX 제헌절 휴장

**사고**: 2026-07-17(수) KRX 휴장(올해부터 재지정) → 틱 0건은 정상, 배치 스킵 아님.

**교훈**: KRX 공휴일 달력 API 연동 필요(아직 미구현). 당분간 수동 일정 확인.

### 7.11 WS ?token= 쿼리 노출

**사고**: HTTP 헤더 제약상 WS는 token을 쿼리 문자열로 전달 → 브라우저 DevTools에서 노출.

**교훈**: stream.py 주석에 고지됨. 토큰이 민감하면 2단계(Cloudflare Access) 병행 필수.

### 7.12 당일분봉 소형주/휴장일 0건 수집

**사고**: 소형주나 휴장일 → KIS 당일분봉이 빈 배열 → 차트 안 그려짐.

**교훈**: 설계상 정상 (yfinance 폴백 또는 과거 데이터 재사용). MACD 35봉 필요해서 며칠 누적돼야 판정 신뢰.

---

## 8. 백로그 (미결·검증 체크리스트)

### [검증] Phase 1 Web 실제 거래일 테스트 (2026-07-20 월)

- [ ] **① 실시간 틱 실제 흐름** — 카드 플래시(1초 이내) 작동, 가격/등락률 갱신 정상
- [ ] **② PINGPONG echo 수정의 세션 유지** — ws.send() 변경 후 KIS 40초 강제 끊김 해결 확인
- [ ] **③ KIS 당일분봉 실수집** (소형주 60m) — MACD 35봉 이상 누적되어 첫 판정 나오는지 확인 (며칠 필요)

### [OPEN DECISION] 관심종목 공유 vs 사용자별 분리

**현행**: 3인 모두 같은 watchlist(전역 1개).

**선택지**:
1. 계속 공유 (현행, 심플) — 추천 현 단계
2. 멀티유저 (계정·로그인, 각자 watchlist) — medium 복잡도, 미결정

**영향**: watchlist 스키마(사용자 ID 컬럼 추가?) 및 API 변경. 미사용자 요청 전까지 보류.

### [보류 medium — 기술 부채]

1. **Candles per-key 동시요청 락 없음** — 같은 (code, tf)를 2개 요청이 동시에 fetch 가능 → 낭비. Lock 추가 검토.
2. **페이지네이션 증분 수집 없음** — 매번 새 request 시 과거 깊이를 전체 훑음. DB에 저장된 범위 기록해 증분 조회로 최적화 필요.
3. **Collector 60m KIS 콜레이트** — 당일분봉 시간당 1회면 충분한데 30초마다 호출 시도 가능. 더블 체크 필요.
4. **collector.py stop()의 _thread.join(timeout=5) 상징적** — 더 긴 timeout 또는 강제 정리 로직 필요(kis_ws.py의 stop()은 태스크 cancel 후 timeout 없이 await하므로 무제한 대기 위험).

### [로드맵] Phase 2~3

**Phase 2 v2**: 틱 실시간 수신 → 진행중 봉 합성 → 차트 실시간 갱신 + 실시간 참고 판정
- 구현: collector 매 틱 수신 후 현재 시간대 진행중 캔들 업데이트

**Phase 3**: 백테스트, 트랙레코드 시스템, 텔레그램 알림
- 시계열 누적(candles 활용)으로 과거 판정 재현 가능

**미래 우선순위 (의원 의견)**:
- 레벨 A: 미등록 종목 즉시 조회 (없는 종목 핸들링)
- 레벨 B: 전시장 배치 스크리닝 (2~5분, 대량 스캔)
- 레벨 C: 트랙레코드 대시보드

### [부채] 자동 테스트 부재

- pytest 프레임워크 0개 (구축 필수)
- 최우선: indicators(MACD/RSI/BB), 리샘플 유틸, 점수 계산 로직
- 다음: collector, candles 신선도 게이트

---

## 9. 운영 치트시트

### 9.1 Docker 명령

```bash
# 재시작 (최신 코드 + .env 반영)
docker compose down
docker compose up -d --build

# 로그 확인 (실시간)
docker compose logs -f mystockbot-api

# DB 초기화 (위험!)
rm -rf data/mystockbot.db
docker compose restart mystockbot-api

# 컨테이너 점검
docker ps
docker inspect mystockbot-api
```

### 9.2 Stock Master 갱신

```bash
# 평일 매일 16:00 실행 (APScheduler cron), 단 stock_master가 7일 이상 stale일 때만 실제 다운로드 수행
# 또는 강제 갱신:
python3 -c "import sys; sys.path.insert(0, 'src'); import stock_master; stock_master.refresh_stock_master()"
```

### 9.3 KIS 토큰 갱신

kis_auth.py는 approval_key 23h 캐시 → 자동. 로그에서 확인:
```bash
docker compose logs | grep "KIS.*approval_key\|KIS.*token"
```

### 9.4 로그 필터링

```bash
# 수집 루프 로그
docker compose logs mystockbot-api | grep "Collector"

# KIS WS 로그
docker compose logs mystockbot-api | grep "KIS\|kis_ws"

# 에러만
docker compose logs mystockbot-api | grep "ERROR\|Exception"

# 시간대별 (최근 1시간)
docker compose logs --since 1h mystockbot-api
```

### 9.5 Cloudflare Tunnel 상태

```bash
# 터널 정보
cloudflared tunnel info mystockbot

# 활성 연결 확인
cloudflared tunnel logs mystockbot

# 재시작
cloudflared tunnel restart mystockbot
# 또는 시스템 서비스
sudo systemctl restart cloudflared
```

### 9.6 Vercel 배포

```bash
cd web
vercel env list  # 환경변수 확인
vercel deploy --prod  # 재배포
```

### 9.7 토큰 재생성

```bash
# 새 토큰 생성
NEW_TOKEN=$(openssl rand -hex 32)
echo "MYSTOCKBOT_API_TOKEN=$NEW_TOKEN" | tee -a .env

# 재시작
docker compose restart mystockbot-api

# 브라우저: TokenBanner에서 새 토큰 입력 (localStorage 갱신)
```

### 9.8 성능 점검

**응답시간 목표**:
- /api/snapshot: **< 5ms**
- /api/stocks/search: **< 50ms**
- /api/stocks/{code}/candles: **신선(600s 이내): < 50ms**, 신선하지 않음: **< 2초**(fetch 필요)

**확인 명령**:
```bash
# 로컬에서 시간 측정
time curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/snapshot

# 혹은 브라우저 DevTools Network 탭
```

### 9.9 DB 백업

```bash
cp data/mystockbot.db data/mystockbot.db.$(date +%Y%m%d).bak
```

### 9.10 VPS 이사 (향후)

1. DB + .env 백업
2. VPS(Oracle Always Free/AWS EC2)에 복사
3. docker-compose up -d --build
4. Cloudflare Tunnel IP 갱신

---

## 10. 참고: 초기 cron 배치 스크립트 구조 (분리·불변)

MyStockBot 피벗 전 GitHub Actions 일일 배치:
- **경로**: src/main.py → pipeline.py → crawler.fetch_all
- **목적**: Google Sheets + 이메일 알림(초기 사용자 요청)
- **상태**: 현행 웹앱과 독립, 불변 유지 (기여 시 손 X)

웹앱 활성화로 이 배치는 선택사항. 개발자 본인 이외는 사용하지 않음.

---

**마지막 갱신**: 2026-07-18
**담당**: vi.joon (개발자)
**다음 검토**: Phase 2 구현 완료 후
