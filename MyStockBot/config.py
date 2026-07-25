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
# 주식일별분봉조회(1분봉, 과거 일자 조회 가능): inquire-time-dailychartprice / FHKST03010230
# 출처(추측 아님 — WebFetch/curl 로 원문 확인):
#   github.com/koreainvestment/open-trading-api
#   examples_llm/domestic_stock/inquire_time_dailychartprice/inquire_time_dailychartprice.py (L23 URL, L71 tr_id)
#   backtester/kis_backtest/providers/kis/data.py L150-225 (_get_minute_bars 페이징 구현)
# 주의: 응답 output2 의 종가 필드는 stck_prpr(주식 현재가) — 일봉 경로의 stck_clpr 이 아니다.
# 국내주식(J)은 1분봉 고정이라 60분봉은 직접 제공되지 않고 리샘플이 필요하다.
KIS_MINUTE_CHART_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"

KIS_FINANCIAL_RATIO_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/financial-ratio"
KIS_INCOME_STMT_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/income-statement"
# 국내업종 일자별 지수 시세(코스피/코스닥 지수): inquire-daily-indexchartprice / FHKUP03500100
# (server/services/indices.py 가 사용 — 실패 시 yfinance 폴백)
KIS_INDEX_CHART_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice"

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

# 60분봉을 KIS 분봉(FHKST03010230) 1차 → yfinance 폴백으로 조회할지.
#
# **기본 비활성.** 켜기 전에 알아야 할 것:
#   · 호출량: 1회 호출당 최대 120건(1분봉)이라 하루치(390분)에 약 4회. 60분봉 MACD 에
#     35봉 이상이 필요하고 하루 약 6.5봉이므로 종목당 초기 백필에 24~32회 호출이 든다.
#     kis_auth.kis_throttle() 이 프로세스 전역으로 0.5초 간격을 강제하므로 종목당 약 15초,
#     종목이 많으면 KIS 유량제한(EGW00201)에 걸릴 수 있다.
#   · 이 저장소는 KIS 자격증명 없이 개발되어 **실제 응답으로 검증되지 않았다.** 필드명·
#     페이징은 공식 예제 3곳 교차확인이지만 첫 실호출 때 스키마를 로그로 확인해야 한다
#     (crawler.fetch_kis_minute_ohlcv 가 첫 성공 응답의 키 목록을 1회 INFO 로 남긴다).
# 켜는 절차는 README '60분봉 데이터 소스' 절 참고.
KIS_MINUTE_ENABLED = os.environ.get("KIS_MINUTE_ENABLED", "").strip().lower() in (
    "1", "true", "yes", "on",
)
# 초기 백필 시 되돌아볼 영업일 수(60분봉 35봉 ≈ 6영업일 + 여유).
KIS_MINUTE_BACKFILL_DAYS = int(os.environ.get("KIS_MINUTE_BACKFILL_DAYS", "10"))

# 시장 지수(server/services/indices.py) read-through 캐시 TTL(초).
# 지수는 개별 종목보다 갱신 빈도가 낮아도 되므로 넉넉히 둔다.
INDICES_CACHE_TTL_SECONDS = int(os.environ.get("INDICES_CACHE_TTL_SECONDS", "60"))

# 모의투자(server/services/paper.py) 초기 가상 시드머니(원). 개인용 단일 계좌.
PAPER_SEED_DEFAULT = int(os.environ.get("PAPER_SEED_DEFAULT", "10000000"))

# 종목마스터(전 종목 검색용) 관련 설정
# 다운로드 URL은 KIS 공식 예제(open-trading-api/stocks_info/kis_*_code_mst.py)와 동일.
# 인증 불필요(공개 정적 파일), 대신 해당 서버가 자체서명/구식 인증서라 SSL 검증을 끈다
# (공식 예제도 ssl._create_unverified_context 로 동일하게 우회함).
KIS_MASTER_URLS = {
    "KOSPI": "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip",
    "KOSDAQ": "https://new.real.download.dws.co.kr/common/master/kosdaq_code.mst.zip",
}
STOCK_MASTER_STALE_DAYS = 7
