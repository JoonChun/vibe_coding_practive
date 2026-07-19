import os

TIMEZONE = "Asia/Seoul"

SHEET_DASHBOARD = "Dashboard"
SHEET_STOCKDATA = "StockData"

STOCK_CODE_LENGTH = 6

STOCKDATA_HEADER = [
    "날짜", "종목코드", "종목명",
    "시가", "종가", "저가", "고가", "거래량",
    "MACD(1일봉)", "RSI(1일봉)", "MACD(60분봉)", "RSI(60분봉)",
    "단기관점", "장기관점",
    "BB_Upper", "BB_Mid", "BB_Lower",
    "PER", "PBR", "ROE", "매출액", "순이익"
]

# KIS API
KIS_BASE_URL = "https://openapi.koreainvestment.com:9443"
KIS_TOKEN_URL = f"{KIS_BASE_URL}/oauth2/tokenP"
# 실시간 체결 WS 인증용 approval_key 발급(REST) — src/kis_auth.py 의 get_approval_key() 가 사용.
KIS_APPROVAL_URL = f"{KIS_BASE_URL}/oauth2/Approval"
# 실시간 시세 WS 접속 주소(실전 도메인) — server/services/kis_ws.py 가 사용.
KIS_WS_URL = "ws://ops.koreainvestment.com:21000"
# 기간별 시세(일봉, 최대 100건): inquire-daily-itemchartprice / FHKST03010100
# (기존 inquire-daily-price(FHKST01010100)는 날짜범위 미지원·output2 미반환이라 항상 빈 응답이었음)
KIS_DAILY_PRICE_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
# 주식당일분봉조회(당일 1분봉, 호출당 최대 30건): inquire-time-itemchartprice / FHKST03010200
# 출처(WebFetch 공식 확인, 추측 아님): raw.githubusercontent.com/koreainvestment/open-trading-api
# /main/examples_llm/domestic_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py
# — src/crawler.py 의 fetch_kis_minutes() 상단 주석에 세부 근거 기록.
KIS_MINUTE_PRICE_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
KIS_FINANCIAL_RATIO_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/financial-ratio"
KIS_INCOME_STMT_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/income-statement"

# KIS 환경변수 키
KIS_APP_KEY_ENV = "KIS_APP_KEY"
KIS_APP_SECRET_ENV = "KIS_APP_SECRET"
KIS_ACCOUNT_NO_ENV = "KIS_ACCOUNT_NO"

# 기술지표 파라미터
OHLCV_LOOKBACK_DAYS = 60    # RSI/MACD/BB 계산용 과거 일봉 수 (KIS API 최대 100건 제한)
KIS_RATE_LIMIT_DELAY = 0.5  # 초, KIS API 호출 간격
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2

# 눌림목(pullback) 판정 파라미터 — 정배열 추세 + MA20 되돌림 후 반등 매수 시그널(indicators.pullback_signal).
PULLBACK_MA_SHORT = 5                  # 단기 이평 — 정배열(MA5>MA20>MA60) 판정의 최단선
PULLBACK_MA_MID = 20                   # 중기 이평 — 눌림목 되돌림 기준선(근접·이탈 판정 대상)
PULLBACK_MA_LONG = 60                  # 장기 이평 — 정배열·추세 필터의 최장선
PULLBACK_MA_SLOPE_LOOKBACK = 5         # MA20 기울기 판정 룩백(봉수) — N봉 전 대비 상승 여부
PULLBACK_PROXIMITY_PCT = 2.0           # MA20 근접밴드 폭(%): |Close-MA20|/MA20 이내면 "눌림 구간"
PULLBACK_MAX_DEPTH_PCT = 10.0          # 전고점 대비 최대 허용 하락폭(%) — 통상 정상 조정폭 상한
PULLBACK_SWING_HIGH_LOOKBACK = 20      # 전고점(swing high) 탐색 룩백(봉수)
PULLBACK_VOL_MA_PERIOD = 50            # 거래량 이동평균 기간
PULLBACK_VOL_CONTRACTION_RATIO = 0.6   # 눌림 진행중 거래량 수축 기준(VCP 이론 통상 0.4~0.6 채택)
PULLBACK_VOL_EXPANSION_RATIO = 1.4     # 반등 확인용 거래량 팽창 기준(평균 대비 140%)
PULLBACK_ADX_PERIOD = 14               # ADX 기간(업계 표준값)
PULLBACK_ADX_TREND_MIN = 20            # 추세 존재 판정 최소 ADX(업계 표준 임계값 20)
PULLBACK_EXIT_PCT = 4.0                # MA20 대비 이 이상 하회 시 "눌림 이탈(무효)" — 지지 붕괴 기준
PULLBACK_MIN_BARS = 65                 # 판정 최소 유효 봉수(MA60 계산 + 기울기 룩백 여유분)

# 신규 관심종목 60분봉 초기 적재(collector._bootstrap_60m_if_needed) 재시도 쿨다운(초).
# _financials_cache 와 동일한 in-memory 쿨다운 패턴(짧은 주기로 실패한 종목을 계속 재호출하지 않기 위함).
SIXTY_MIN_BOOTSTRAP_RETRY_COOLDOWN_SECONDS = 600

CREDENTIALS_ENV_KEY = "GOOGLE_CREDENTIALS_JSON"
SPREADSHEET_ID_ENV_KEY = "SPREADSHEET_ID"
GMAIL_APP_PASSWORD_ENV_KEY = "GMAIL_APP_PASSWORD"
NOTIFY_EMAIL_ENV_KEY = "NOTIFY_EMAIL"
SENDER_EMAIL_ENV_KEY = "SENDER_EMAIL"
API_TOKEN_ENV_KEY = "MYSTOCKBOT_API_TOKEN"

# 서버(Phase 1) 관련 설정
DB_PATH = os.environ.get(
    "MYSTOCKBOT_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "mystockbot.db"),
)
SNAPSHOT_CACHE_TTL_SECONDS = int(os.environ.get("SNAPSHOT_CACHE_TTL_SECONDS", "20"))
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

# 수집 루프(server/services/collector.py) 사이클 간격(초)
COLLECTOR_INTERVAL_MARKET = 30   # 장중(평일 09:00~15:40 Asia/Seoul)
COLLECTOR_INTERVAL_IDLE = 600    # 그 외 시간대

# 틱 합성기(server/services/tick_aggregator.py) 관련 설정
TICK_AGG_BAR_BROADCAST_INTERVAL_SECONDS = int(
    os.environ.get("TICK_AGG_BAR_BROADCAST_INTERVAL_SECONDS", "2")
)
TICK_AGG_REFERENCE_INTERVAL_SECONDS = int(
    os.environ.get("TICK_AGG_REFERENCE_INTERVAL_SECONDS", "5")
)
TICK_AGG_RING_BUFFER_MAX_MINUTES = int(
    os.environ.get("TICK_AGG_RING_BUFFER_MAX_MINUTES", "400")
)

# 종목마스터(전 종목 검색용) 관련 설정
# 다운로드 URL은 KIS 공식 예제(open-trading-api/stocks_info/kis_*_code_mst.py)와 동일.
# 인증 불필요(공개 정적 파일), 대신 해당 서버가 자체서명/구식 인증서라 SSL 검증을 끈다
# (공식 예제도 ssl._create_unverified_context 로 동일하게 우회함).
KIS_MASTER_URLS = {
    "KOSPI": "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
    "KOSDAQ": "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
}
STOCK_MASTER_STALE_DAYS = 7
