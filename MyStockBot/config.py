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
# 기간별 시세(일봉, 최대 100건): inquire-daily-itemchartprice / FHKST03010100
# (기존 inquire-daily-price(FHKST01010100)는 날짜범위 미지원·output2 미반환이라 항상 빈 응답이었음)
KIS_DAILY_PRICE_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
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
