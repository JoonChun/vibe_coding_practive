import logging
import os

_logger = logging.getLogger(__name__)

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

# 국내휴장일조회: chk-holiday / CTCA0903R [국내주식-040]
# 출처(추측 아님 — curl 로 원문 확인):
#   github.com/koreainvestment/open-trading-api
#   examples_llm/domestic_stock/chk_holiday/chk_holiday.py (L23 URL, L72 tr_id, L74-78 params)
#   .../chk_chk_holiday.py COLUMN_MAPPING (응답 필드: bass_dt·wday_dvsn_cd·bzdy_yn·
#                                          tr_day_yn·opnd_yn·sttl_day_yn)
#
# ★ 공식 docstring 경고: "당사 원장서비스와 연관되어 있어 단시간 내 다수 호출시 서비스에
#   영향을 줄 수 있어 가급적 1일 1회 호출 부탁드립니다." → 결과를 SQLite 에 영속 캐시하고
#   하루 1회만 갱신한다(KIS_HOLIDAY_MIN_REFRESH_HOURS).
# ★ 개장일 판단은 opnd_yn(개장일여부)을 쓴다 — 공식 docstring 이 명시한 필드다.
KIS_HOLIDAY_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/chk-holiday"

KIS_FINANCIAL_RATIO_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/financial-ratio"
KIS_INCOME_STMT_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/income-statement"
# 국내업종 일자별 지수 시세(코스피/코스닥 지수): inquire-daily-indexchartprice / FHKUP03500100
# (server/services/indices.py 가 사용 — 실패 시 yfinance 폴백)
KIS_INDEX_CHART_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice"

# 국내업종 현재지수: inquire-index-price / FHPUP02100000 [v1_국내주식-063]
# 출처(추측 아님 — curl 로 원문 확인):
#   github.com/koreainvestment/open-trading-api
#   examples_llm/domestic_stock/inquire_index_price/inquire_index_price.py (L25 URL, L73 tr_id)
#   .../chk_inquire_index_price.py COLUMN_MAPPING (응답 필드 전체)
# 일자별 지수(FHKUP03500100)와 달리 **전일 대비·대비율을 직접** 주고, 게다가
# 상승/보합/하락/상한/하한 종목 수(시장 폭)까지 같은 응답에 담겨 온다.
KIS_INDEX_PRICE_URL = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-index-price"

# KIS 환경변수 키
# (KIS_ACCOUNT_NO 는 제거 — 조회 전용 앱이라 계좌번호를 읽는 코드가 저장소에 없었다.
#  사용하지 않는 민감정보를 .env·GitHub Secrets 에 유통하는 것은 유출 표면만 넓힌다.
#  주문 API 를 붙이는 날 다시 도입한다.)
KIS_APP_KEY_ENV = "KIS_APP_KEY"
KIS_APP_SECRET_ENV = "KIS_APP_SECRET"

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

# 눌림목(pullback) 판정 파라미터 — 정배열 추세 + MA20 되돌림 후 반등(indicators.pullback_signal).
# 5단계 판정(decision_rules)과는 **별개의 축**이다: 그쪽은 "지금 어느 국면인가", 이쪽은
# "지금이 진입 타이밍인가"를 본다. 점수에 합산되지 않으므로 판정 결과를 바꾸지 않는다.
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

CREDENTIALS_ENV_KEY = "GOOGLE_CREDENTIALS_JSON"
SLACK_WEBHOOK_URL_ENV_KEY = "SLACK_WEBHOOK_URL"
DISCORD_WEBHOOK_URL_ENV_KEY = "DISCORD_WEBHOOK_URL"
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

# ★ 실패는 성공과 같은 TTL 로 캐시하면 안 된다.
# 예전 구현은 조회 실패 항목까지 60초 동안 그대로 재사용했다. 그래서 순간적인 네트워크
# 장애 하나가 "데이터 없음" 화면을 60초 고정시키고, 네트워크가 1초 뒤 복구돼도 사용자는
# 남은 59초를 계속 실패 화면으로 봤다(새로고침해도 캐시가 응답한다).
# 실패 항목은 짧게만 붙잡고 곧 재시도한다.
INDICES_ERROR_RETRY_SECONDS = int(os.environ.get("INDICES_ERROR_RETRY_SECONDS", "10"))

# 조회가 실패했을 때 "마지막으로 성공한 값"을 stale 로 표시해 내주는 최대 기간(초).
# 이 시간을 넘으면 낡은 값을 내주는 대신 실패로 표시한다 — 몇 시간 전 지수를 현재값처럼
# 보여주는 것이 "데이터 없음"보다 나쁘기 때문이다. 응답에는 항상 stale 여부와 경과
# 초(stale_age_seconds)를 함께 실어 화면이 낡음을 표시할 수 있게 한다.
INDICES_STALE_MAX_SECONDS = int(os.environ.get("INDICES_STALE_MAX_SECONDS", "900"))

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

# ────────────────────────────────────────────
# 판정 전환 알림 (server/services/alerts.py)
#
# **기본 비활성.** 켜기 전에 알아야 할 것 — 아래 값들은 모두 "알림 폭풍"을 막기 위한
# 장치이고, 각각 실제 코드에서 확인된 오알림 경로에 대응한다(README '판정 전환 알림' 절).
# ────────────────────────────────────────────
def _env_flag(key: str, default: str = "") -> bool:
    # 빈 대입(`KEY=`)이 문서화된 기본값을 뒤집지 않도록 `or default` 로 받는다.
    return (os.environ.get(key) or default).strip().lower() in ("1", "true", "yes", "on")


DECISION_ALERT_ENABLED = _env_flag("DECISION_ALERT_ENABLED")

# 감시할 판정 종류. "short"(60분봉) / "long"(일봉+재무) 중 콤마로 선택. 대소문자 무관.
#
# 오타·대문자를 조용히 버리면 빈 튜플이 되고, kinds=() 인 diff() 는 전환도 시딩도 하지
# 않아 **알림 기능 전체가 무음으로 죽는다.** 그런데 /api/alerts/config 의 enabled 는
# 여전히 true 라 진단 신호가 사실상 없다. 그래서 관용적으로 파싱하고, 버린 토큰은 경고로
# 남기고, 결과가 비면 기본값으로 되돌린다.
_DECISION_ALERT_VIEW_CHOICES = ("short", "long")


def _parse_alert_views(raw: str) -> tuple[str, ...]:
    tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
    valid = tuple(t for t in tokens if t in _DECISION_ALERT_VIEW_CHOICES)
    dropped = [t for t in tokens if t not in _DECISION_ALERT_VIEW_CHOICES]
    if dropped:
        _logger.warning(
            "[config] DECISION_ALERT_VIEWS 에 알 수 없는 값 %s — 허용값은 %s",
            dropped, _DECISION_ALERT_VIEW_CHOICES,
        )
    if not valid:
        _logger.warning(
            "[config] DECISION_ALERT_VIEWS 가 비어 기본값 %s 을 사용합니다",
            _DECISION_ALERT_VIEW_CHOICES,
        )
        return _DECISION_ALERT_VIEW_CHOICES
    # 중복 제거 + 선언 순서 고정
    return tuple(c for c in _DECISION_ALERT_VIEW_CHOICES if c in valid)


DECISION_ALERT_VIEWS = _parse_alert_views(
    os.environ.get("DECISION_ALERT_VIEWS", "short,long")
)

# True 면 '측'(매수측/관망/매도측)이 바뀔 때만 알린다.
# False 로 두면 강력매수→매수 같은 등급 변화도 알리는데, 그건 골든크로스가 다음 봉에
# 소멸하면서 **반드시** 생기는 구조적 사건이라 골든크로스마다 두 번째 알림이 따라온다.
# (decision_rules.view_side 주석 참고)
DECISION_ALERT_SIDE_ONLY = _env_flag("DECISION_ALERT_SIDE_ONLY", "1")

# 같은 판정이 연속 몇 사이클 유지되면 확정으로 볼지(히스테리시스).
# 장중 사이클이 30초라 2면 60초 확정. 장중 마지막 봉은 미완성이므로 한 사이클만 보고
# 알리면 계산 흔들림이 그대로 알림이 된다.
DECISION_ALERT_CONFIRM_CYCLES = max(1, int(os.environ.get("DECISION_ALERT_CONFIRM_CYCLES", "2")))

# 같은 종목·같은 판정 종류에 대한 최소 알림 간격(분).
DECISION_ALERT_COOLDOWN_MINUTES = int(os.environ.get("DECISION_ALERT_COOLDOWN_MINUTES", "60"))

# 기준선(마지막 알린 판정)이 이보다 오래 방치되면 비교하지 않고 조용히 재시딩한다.
# 관심종목에서 뺐다가 한참 뒤 다시 넣는 경우 옛 기준선과 비교해 헛알림이 나가는 것을 막는다.
DECISION_ALERT_STATE_TTL_DAYS = int(os.environ.get("DECISION_ALERT_STATE_TTL_DAYS", "7"))

# 한 메시지에 나열할 최대 전환 건수(초과분은 "외 N건"으로 요약). 전체 건수는 항상 표기한다.
DECISION_ALERT_MAX_ROWS = int(os.environ.get("DECISION_ALERT_MAX_ROWS", "30"))

# 휴장일 캐시 갱신 최소 간격(시간). 공식 문서가 "가급적 1일 1회"를 요청하므로 20시간을 둔다
# (하루 1회 스케줄 + 부팅 시 1회가 겹쳐도 실제 호출은 하루 한 번으로 수렴).
KIS_HOLIDAY_MIN_REFRESH_HOURS = int(os.environ.get("KIS_HOLIDAY_MIN_REFRESH_HOURS", "20"))
# 한 번 갱신할 때 앞으로 며칠치를 확보할지(페이징으로 받는다).
KIS_HOLIDAY_LOOKAHEAD_DAYS = int(os.environ.get("KIS_HOLIDAY_LOOKAHEAD_DAYS", "400"))
