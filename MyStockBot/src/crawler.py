import logging
import math
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import pandas as pd
import yfinance as yf

from config import (
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_DAILY_PRICE_URL,
    KIS_FINANCIAL_RATIO_URL,
    KIS_HOLIDAY_URL,
    KIS_INCOME_STMT_URL,
    KIS_MINUTE_CHART_URL,
    KIS_RATE_LIMIT_DELAY,
    OHLCV_LOOKBACK_DAYS,
    TIMEZONE,
)
import indicators
import kis_auth

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────
# 공통 유틸
# ────────────────────────────────────────────

def _to_float(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _to_int(val) -> int | None:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _price_change(df: pd.DataFrame) -> dict:
    """일봉 df 마지막 2개 종가로 전일 대비 등락폭·등락률 계산. 데이터부족 시 None."""
    if df is None or len(df) < 2:
        return {"change": None, "change_pct": None}
    prev_close = _to_float(df.iloc[-2]["close"])
    curr_close = _to_float(df.iloc[-1]["close"])
    if prev_close is None or curr_close is None or prev_close == 0:
        return {"change": None, "change_pct": None}
    change = round(curr_close - prev_close, 2)
    change_pct = round((curr_close - prev_close) / prev_close * 100, 2)
    return {"change": change, "change_pct": change_pct}


def _bar_date(df: pd.DataFrame) -> str | None:
    """일봉 df 마지막 봉의 거래일을 'YYYY-MM-DD' 로 반환. 파싱 실패 시 None.

    수집 실행일(오늘)이 아니라 **데이터가 실제로 속한 거래일**이다. 호출부(src/main.py)가
    이 값을 시트 '날짜' 컬럼에 쓰기 때문에, 휴장일에 크론이 돌아 직전 거래일 종가를
    받아와도 그 종가의 원래 날짜로 기록된다 → sheets.write_stock_data 의 (날짜,종목코드)
    중복 스킵이 자연히 걸려 같은 종가가 다른 날짜로 두 번 쌓이지 않는다.
    """
    if df is None or len(df) == 0:
        return None
    raw = str(df.iloc[-1].get("date") or "")[:8]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


_EMPTY_RESULT = {
    "open": None, "close": None, "low": None, "high": None, "volume": None,
    "change": None, "change_pct": None,
    "bar_date": None,
    "macd_1d": None, "rsi_1d": None, "macd_60m": None, "rsi_60m": None,
    "rsi_value_1d": None, "rsi_value_60m": None,
    "short_view": None, "long_view": None,
    "bb_upper": None, "bb_mid": None, "bb_lower": None,
    "per": None, "pbr": None, "roe": None,
    "revenue": None, "net_income": None,
    "short_score": None, "long_score": None,
    "source": None, "source_60m": None,
}


# ────────────────────────────────────────────
# KIS API
# ────────────────────────────────────────────

def _get_headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": os.environ.get(KIS_APP_KEY_ENV, ""),
        "appsecret": os.environ.get(KIS_APP_SECRET_ENV, ""),
    }


def fetch_kis_ohlcv(code: str, token: str, period: str, lookback_days: int) -> pd.DataFrame | None:
    """KIS 기간별시세(FHKST03010100) 조회 일반화.

    period: FID_PERIOD_DIV_CODE ("D"=일봉, "W"=주봉, "M"=월봉, "Y"=년봉).
    lookback_days: 조회 시작일을 오늘로부터 며칠 전으로 잡을지(각 tf 별 권장 range는 호출부에서 결정).
    반환 컬럼: date(YYYYMMDD 문자열)/open/high/low/close/volume. 실패·빈 데이터 시 None.
    """
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz)
    start = today - timedelta(days=lookback_days)

    headers = _get_headers(token)
    headers["tr_id"] = "FHKST03010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": period,
        "FID_ORG_ADJ_PRC": "0",
    }
    try:
        kis_auth.kis_throttle()
        resp = requests.get(KIS_DAILY_PRICE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[KIS] OHLCV 요청 실패 ({code}, period={period}): {e}")
        return None

    output2 = data.get("output2")
    if not output2:
        logger.info(f"[KIS] OHLCV output2 없음 ({code}, period={period}): rt_cd={data.get('rt_cd')} msg={data.get('msg1')}")
        return None

    rows = []
    for item in output2:
        try:
            rows.append({
                "date": item["stck_bsop_date"],
                "open": int(item["stck_oprc"]),
                "high": int(item["stck_hgpr"]),
                "low": int(item["stck_lwpr"]),
                "close": int(item["stck_clpr"]),
                "volume": int(item["acml_vol"]),
            })
        except (KeyError, ValueError):
            continue

    if not rows:
        return None

    df = pd.DataFrame(rows)
    return df.sort_values("date").reset_index(drop=True)


# ────────────────────────────────────────────
# KIS 분봉(1분) — 주식일별분봉조회 FHKST03010230
#
# 출처(추측 금지 원칙에 따라 공식 코드 3곳 교차확인):
#   examples_llm/domestic_stock/inquire_time_dailychartprice/inquire_time_dailychartprice.py
#     L23 API_URL, L71 tr_id="FHKST03010230", L73-80 params 6개
#   .../chk_inquire_time_dailychartprice.py L22-39 COLUMN_MAPPING (응답 필드명 전체)
#   backtester/kis_backtest/providers/kis/data.py L150-225 (_get_minute_bars 페이징)
#   MCP/Kis Trading MCP/configs/domestic_stock.json (파라미터 타입·필수여부 교차확인)
#
# 함정 2개:
#   1) 종가 필드가 stck_prpr(주식 현재가)이다. 일봉 경로의 stck_clpr 을 재사용하면 전 종목
#      close 가 None 이 된다 → 파서를 공유하지 않고 분리한다.
#   2) 국내주식(J)은 1분봉 고정이다(간격 지정 파라미터 없음 — 60/120초 지정은 업종 U 전용).
#      60분봉은 리샘플로 만든다.
# ────────────────────────────────────────────

_KIS_MINUTE_TR_ID = "FHKST03010230"
_KIS_MINUTE_PAGE_LIMIT = 120  # 1회 호출 최대 건수(공식 docstring)
_KIS_MINUTE_SESSION_END = "153000"    # 정규장 마감 — 역순 페이징 시작 시각
_KIS_MINUTE_SESSION_START = "090000"  # 정규장 개장 — 여기 도달하면 그 날짜 완료
_KIS_MINUTE_MAX_PAGES = 8  # 390분 / 120건 ≈ 4회. 무한 루프 방지용 상한.

_minute_schema_logged = False


def _log_minute_schema_once(rows: list[dict]) -> None:
    """첫 성공 응답의 output2 키 목록을 1회만 남긴다.

    이 경로는 자격증명 없이 개발되어 실제 응답으로 검증되지 않았다. 필드명이 문서와
    다르면 조용히 전부 None 이 되므로, 실환경 첫 호출에서 스키마를 눈으로 확인할 수 있게 한다.
    """
    global _minute_schema_logged
    if _minute_schema_logged or not rows:
        return
    _minute_schema_logged = True
    logger.info("[KIS] 분봉 output2 스키마(첫 응답 1회만): %s", sorted(rows[0].keys()))


def _parse_kis_minute_rows(rows: list[dict]) -> list[dict]:
    """분봉 output2 → [{date: 'YYYYMMDDHHMM', open/high/low/close/volume}]. 파싱 실패 행은 건너뜀."""
    parsed = []
    for item in rows:
        raw_date = str(item.get("stck_bsop_date") or "").strip()
        raw_time = str(item.get("stck_cntg_hour") or "").strip()
        if len(raw_date) != 8 or len(raw_time) < 4:
            continue
        try:
            parsed.append({
                "date": f"{raw_date}{raw_time[:4]}",  # 분 단위까지(초는 버린다)
                "open": float(item["stck_oprc"]),
                "high": float(item["stck_hgpr"]),
                "low": float(item["stck_lwpr"]),
                # ★ 분봉 종가는 stck_prpr — 일봉의 stck_clpr 이 아니다.
                "close": float(item["stck_prpr"]),
                "volume": int(float(item.get("cntg_vol") or 0)),
                "_time": raw_time,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return parsed


def _fetch_kis_minute_one_day(code: str, token: str, date_str: str) -> list[dict]:
    """특정 일자의 1분봉 전체를 시각 역순 페이징으로 모아 반환(오름차순 정렬).

    페이징 방식은 공식 백테스터와 동일: FID_INPUT_HOUR_1 을 마감 시각으로 시작해, 응답의
    최소 체결시각을 다음 호출의 기준시각으로 재투입한다. 개장 시각 도달·건수 미달·상한
    도달 중 하나면 종료.
    """
    headers = _get_headers(token)
    headers["tr_id"] = _KIS_MINUTE_TR_ID

    collected: dict[str, dict] = {}  # date(분) → row, 페이지 경계 중복 제거
    cursor = _KIS_MINUTE_SESSION_END

    for _ in range(_KIS_MINUTE_MAX_PAGES):
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_HOUR_1": cursor,
            "FID_INPUT_DATE_1": date_str,
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_FAKE_TICK_INCU_YN": "",
        }
        try:
            kis_auth.kis_throttle()
            resp = requests.get(
                KIS_MINUTE_CHART_URL, headers=headers, params=params, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("[KIS] 분봉 요청 실패 (%s, %s, %s): %s", code, date_str, cursor, e)
            break

        rows = data.get("output2") or []
        if not rows:
            if not collected:
                logger.info(
                    "[KIS] 분봉 output2 없음 (%s, %s): rt_cd=%s msg=%s",
                    code, date_str, data.get("rt_cd"), data.get("msg1"),
                )
            break

        _log_minute_schema_once(rows)
        parsed = _parse_kis_minute_rows(rows)
        if not parsed:
            break

        for row in parsed:
            collected.setdefault(row["date"], row)

        min_time = min(row["_time"] for row in parsed)
        if min_time <= _KIS_MINUTE_SESSION_START or len(rows) < _KIS_MINUTE_PAGE_LIMIT:
            break
        cursor = min_time

    ordered = sorted(collected.values(), key=lambda r: r["date"])
    for row in ordered:
        row.pop("_time", None)
    return ordered


def fetch_kis_minute_ohlcv(code: str, token: str, lookback_days: int) -> pd.DataFrame | None:
    """최근 영업일들의 1분봉을 모아 반환. 컬럼: date('YYYYMMDDHHMM')/open/high/low/close/volume.

    1회 호출 = 1일자라서 날짜 루프 + 날짜 내 시각 역순 페이징의 2중 루프다. 주말·휴장일은
    market_calendar 로 건너뛴다(빈 응답 왕복 낭비 방지). 수집 결과가 없으면 None.
    """
    import market_calendar

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz).date()

    rows: list[dict] = []
    checked = 0
    day_offset = 0
    # lookback_days 만큼의 '거래일'을 모을 때까지 달력을 거슬러 올라간다(최대 2배까지만 탐색).
    while checked < lookback_days and day_offset < lookback_days * 2 + 10:
        target = today - timedelta(days=day_offset)
        day_offset += 1
        if not market_calendar.is_trading_day(target):
            continue
        checked += 1
        rows.extend(_fetch_kis_minute_one_day(code, token, target.strftime("%Y%m%d")))

    if not rows:
        return None

    df = pd.DataFrame(rows)
    return df.sort_values("date").reset_index(drop=True)


def resample_minutes_to_60m(df: pd.DataFrame) -> pd.DataFrame | None:
    """1분봉 df('date'='YYYYMMDDHHMM') → 60분봉. tz-aware DatetimeIndex 를 붙여 반환.

    반환 형식은 crawler.fetch_yf_ohlcv 와 같은 계약(date 문자열 컬럼 + tz-aware 인덱스)이라
    호출부(collector._get_60m_df → _df_to_candle_items_minute)가 소스에 무관하게 동작한다.

    **진행 중인 마지막 봉은 버린다.** 아직 닫히지 않은 60분 구간은 미완성 OHLC 라서 지표에
    넣으면 판정이 봉 중간마다 흔들린다(공식 문서도 첫 배열의 체결량이 직전 봉 값일 수 있다고
    경고한다). 장중에는 그래서 마지막 미완성 구간을 제외한다.
    """
    if df is None or df.empty or "date" not in df.columns:
        return None

    tz = ZoneInfo(TIMEZONE)
    ts = pd.to_datetime(df["date"], format="%Y%m%d%H%M", errors="coerce")
    work = df.assign(_ts=ts).dropna(subset=["_ts"])
    if work.empty:
        return None
    work = work.set_index("_ts").sort_index()

    agg = work.resample("60min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
    }).dropna(subset=["open", "high", "low", "close"])
    if agg.empty:
        return None

    # 마지막 구간이 아직 진행 중이면(마지막 1분봉이 그 구간의 끝에 닿지 않았으면) 버린다.
    last_bin = agg.index[-1]
    if work.index[-1] < last_bin + pd.Timedelta(minutes=59):
        agg = agg.iloc[:-1]
    if agg.empty:
        return None

    idx = agg.index.tz_localize(tz)
    out = pd.DataFrame({
        "date": idx.strftime("%Y%m%d%H%M"),
        "open": agg["open"].astype(float),
        "high": agg["high"].astype(float),
        "low": agg["low"].astype(float),
        "close": agg["close"].astype(float),
        "volume": agg["volume"].astype(int),
    })
    out.index = idx
    return out


# ────────────────────────────────────────────
# KRX 휴장일 조회 — 국내휴장일조회 CTCA0903R
#
# 출처: examples_llm/domestic_stock/chk_holiday/chk_holiday.py (URL·tr_id·params·페이징),
#       .../chk_chk_holiday.py COLUMN_MAPPING (응답 필드).
#
# ★ 공식 docstring 경고: "원장서비스와 연관되어 있어 단시간 내 다수 호출시 서비스에 영향을
#   줄 수 있어 가급적 1일 1회 호출" → 호출부(scheduler)가 하루 1회로 제한하고 결과를
#   SQLite 에 영속 저장한다. 이 함수 자체는 호출 빈도를 판단하지 않는다.
# ★ 개장일 판단은 opnd_yn — 공식 docstring 이 "주문을 넣을 수 있는지 확인하고자 하실
#   경우 개장일여부(opnd_yn)을 사용"이라고 명시한다.
# ────────────────────────────────────────────

_KIS_HOLIDAY_TR_ID = "CTCA0903R"
# 응답 1페이지가 몇 건인지 문서화되어 있지 않아, 연속조회 헤더(tr_cont M/F)를 따라가되
# 무한 루프 방지 상한을 둔다.
_KIS_HOLIDAY_MAX_PAGES = 12
_KIS_HOLIDAY_CONTINUE_FLAGS = ("M", "F")


def _parse_kis_holiday_rows(rows: list[dict]) -> list[dict]:
    """휴장일 output → [{date: 'YYYY-MM-DD', is_open: bool}]. 파싱 실패 행은 건너뜀."""
    parsed = []
    for item in rows:
        raw_date = str(item.get("bass_dt") or "").strip()
        if len(raw_date) != 8 or not raw_date.isdigit():
            continue
        opnd = str(item.get("opnd_yn") or "").strip().upper()
        if opnd not in ("Y", "N"):
            continue
        parsed.append({
            "date": f"{raw_date[0:4]}-{raw_date[4:6]}-{raw_date[6:8]}",
            "is_open": opnd == "Y",
        })
    return parsed


def fetch_kis_holidays(token: str, bass_dt: str, max_days: int) -> list[dict]:
    """기준일자부터의 개장일 여부를 연속조회로 모아 반환. 실패 시 빈 리스트.

    반환: [{date: 'YYYY-MM-DD', is_open: bool}, ...] (날짜 오름차순, 중복 제거)
    max_days 만큼 모이거나 연속조회가 끝나면 종료한다.
    """
    headers = _get_headers(token)
    headers["tr_id"] = _KIS_HOLIDAY_TR_ID
    headers["tr_cont"] = ""

    collected: dict[str, dict] = {}
    ctx_fk = ""
    ctx_nk = ""

    for page in range(_KIS_HOLIDAY_MAX_PAGES):
        params = {"BASS_DT": bass_dt, "CTX_AREA_FK": ctx_fk, "CTX_AREA_NK": ctx_nk}
        try:
            kis_auth.kis_throttle()
            resp = requests.get(KIS_HOLIDAY_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("[KIS] 휴장일 조회 실패 (page=%d, bass_dt=%s): %s", page, bass_dt, e)
            break

        rows = data.get("output") or []
        if isinstance(rows, dict):  # 단건 응답 변형 방어
            rows = [rows]
        parsed = _parse_kis_holiday_rows(rows)
        if not parsed:
            if not collected:
                logger.warning(
                    "[KIS] 휴장일 output 없음/파싱 실패: rt_cd=%s msg=%s",
                    data.get("rt_cd"), data.get("msg1"),
                )
            break

        for row in parsed:
            collected.setdefault(row["date"], row)

        if len(collected) >= max_days:
            break

        # 연속조회: 응답 헤더 tr_cont 가 M/F 면 다음 페이지가 있고, 바디의 ctx_area_* 를
        # 다음 요청에 되돌려준다(공식 예제와 동일).
        tr_cont = (resp.headers.get("tr_cont") or "").strip().upper()
        if tr_cont not in _KIS_HOLIDAY_CONTINUE_FLAGS:
            break
        ctx_fk = str(data.get("ctx_area_fk") or "").strip()
        ctx_nk = str(data.get("ctx_area_nk") or "").strip()
        headers["tr_cont"] = "N"

    return sorted(collected.values(), key=lambda r: r["date"])[:max_days]


# 페이지네이션 시 한 호출의 [start, end] 날짜 구간(일수) — period별 근사치.
# KIS 기간별시세는 호출당 최대 100건이므로, 각 tf의 발생 빈도(거래일/주/월)를 감안해
# 한 호출이 대략 100건 근처로 나오도록 잡는다(공휴일만큼 살짝 넉넉하게).
_PAGE_WINDOW_DAYS = {"D": 140, "W": 700, "M": 3000}


def fetch_kis_ohlcv_paged(
    code: str,
    token: str,
    period: str,
    target_count: int,
    max_pages: int = 15,
    end: datetime | None = None,
) -> pd.DataFrame | None:
    """KIS 기간별시세(FHKST03010100)를 날짜 구간을 과거로 옮겨가며 반복 호출해
    최대 target_count건까지 누적한다.

    TR/URL은 fetch_kis_ohlcv(단일 호출, 무변경)와 동일 — 호출당 최대 100건 제한을
    페이지네이션으로 우회한다. end 를 주면 그 시점 이전 구간부터 역행한다
    (candles 서비스의 before 커서 — 차트 왼쪽 스크롤 시 과거 페이지 로딩용).

    페이지네이션 규칙:
      - 첫 호출: end=end(기본 오늘), start=end-윈도우(period별 _PAGE_WINDOW_DAYS).
      - 다음 호출: end=(직전 응답의 가장 이른 날짜 - 1일), start=end-윈도우.
      - 응답이 비거나(원천 고갈) 가장 이른 날짜가 더 과거로 진행하지 못하면 중단.
      - target_count건 이상 모이면 즉시 중단, max_pages 도달 시에도 중단(폭주 방지).
      - 호출 간격은 kis_auth.kis_throttle() 전역 스로틀 하나로만 강제한다
        (별도 sleep 을 겹치지 않는다 — collector.py 가 daily 경로에서 확인한 관례).

    반환: fetch_kis_ohlcv 와 동일 스키마(date 'YYYYMMDD'/open/high/low/close/volume),
    날짜 오름차순, 중복 제거. target_count 초과분은 최신 target_count건만 남긴다.
    실패·빈 데이터 시 None.
    """
    tz = ZoneInfo(TIMEZONE)
    cursor_end = end if end is not None else datetime.now(tz)
    window_days = _PAGE_WINDOW_DAYS.get(period, _PAGE_WINDOW_DAYS["D"])

    all_rows: dict[str, dict] = {}
    earliest_seen: str | None = None

    for page in range(max_pages):
        start = cursor_end - timedelta(days=window_days)

        headers = _get_headers(token)
        headers["tr_id"] = "FHKST03010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": cursor_end.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",
        }
        try:
            kis_auth.kis_throttle()
            resp = requests.get(KIS_DAILY_PRICE_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"[KIS] OHLCV 페이지네이션 요청 실패 ({code}, period={period}, page={page}): {e}")
            break

        output2 = data.get("output2")
        if not output2:
            break

        page_dates = []
        for item in output2:
            try:
                date_str = item["stck_bsop_date"]
                page_dates.append(date_str)
                if date_str not in all_rows:
                    all_rows[date_str] = {
                        "date": date_str,
                        "open": int(item["stck_oprc"]),
                        "high": int(item["stck_hgpr"]),
                        "low": int(item["stck_lwpr"]),
                        "close": int(item["stck_clpr"]),
                        "volume": int(item["acml_vol"]),
                    }
            except (KeyError, ValueError):
                continue

        if not page_dates:
            break

        new_earliest = min(page_dates)
        if earliest_seen is not None and new_earliest >= earliest_seen:
            break  # 더 과거로 진행 못함 — 무한루프 방지
        earliest_seen = new_earliest

        if len(all_rows) >= target_count:
            break

        try:
            cursor_end = datetime.strptime(new_earliest, "%Y%m%d").replace(tzinfo=tz) - timedelta(days=1)
        except ValueError:
            break

    if not all_rows:
        return None

    df = pd.DataFrame(list(all_rows.values())).sort_values("date").reset_index(drop=True)
    if len(df) > target_count:
        df = df.iloc[-target_count:].reset_index(drop=True)
    return df


def _kis_daily_ohlcv(code: str, token: str) -> pd.DataFrame | None:
    """기존 호출부(스냅샷 수집) 전용 — 일봉 지표 계산에 필요한 lookback으로 fetch_kis_ohlcv 호출."""
    lookback = int(OHLCV_LOOKBACK_DAYS * 1.6)
    return fetch_kis_ohlcv(code, token, period="D", lookback_days=lookback)


def _kis_financial_ratio(code: str, token: str) -> dict:
    headers = _get_headers(token)
    headers["tr_id"] = "FHKST66430200"
    params = {
        "FID_DIV_CLS_CODE": "0",
        "fid_input_iscd": code,
        "fid_cond_mrkt_div_code": "J",
    }
    try:
        kis_auth.kis_throttle()
        resp = requests.get(KIS_FINANCIAL_RATIO_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[KIS] 재무비율 요청 실패 ({code}): {e}")
        return {"per": None, "pbr": None, "roe": None}

    output = data.get("output")
    if not output:
        return {"per": None, "pbr": None, "roe": None}

    item = output[0]
    return {
        "per": _to_float(item.get("per")),
        "pbr": _to_float(item.get("pbr")),
        "roe": _to_float(item.get("roe")),
    }


def _kis_income_statement(code: str, token: str) -> dict:
    headers = _get_headers(token)
    headers["tr_id"] = "FHKST66430300"
    params = {
        "FID_DIV_CLS_CODE": "0",
        "fid_input_iscd": code,
        "fid_cond_mrkt_div_code": "J",
    }
    try:
        kis_auth.kis_throttle()
        resp = requests.get(KIS_INCOME_STMT_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"[KIS] 손익계산서 요청 실패 ({code}): {e}")
        return {"revenue": None, "net_income": None}

    output = data.get("output")
    if not output:
        return {"revenue": None, "net_income": None}

    item = output[0]
    return {
        "revenue": _to_int(item.get("sale_account")),
        "net_income": _to_int(item.get("thtr_ntin")),
    }


def fetch_kis_financials(code: str, token: str) -> dict:
    """재무비율(PER/PBR/ROE) + 손익계산서(매출액/순이익) 통합 공개 래퍼.

    기존 private _kis_financial_ratio/_kis_income_statement 를 묶어 collector.py 등
    server 쪽에서 재사용할 수 있도록 노출한다. 두 호출 사이 KIS_RATE_LIMIT_DELAY sleep 포함
    (기존 _fetch_from_kis 와 동일한 호출 간격 관례). 개별 실패는 삼켜서 None 필드로 채운다
    (호출부에서 예외 처리를 강제하지 않기 위함 — 각 하위 함수가 이미 실패 시 None dict 반환).
    """
    ratio_data = _kis_financial_ratio(code, token)
    time.sleep(KIS_RATE_LIMIT_DELAY)
    income_data = _kis_income_statement(code, token)
    return {**ratio_data, **income_data}


def _fetch_from_kis(code: str, name: str, token: str) -> dict | None:
    """KIS API로 전체 데이터 수집. 실패 시 None 반환."""
    df = _kis_daily_ohlcv(code, token)
    if df is None or df.empty:
        return None

    time.sleep(KIS_RATE_LIMIT_DELAY)
    latest = df.iloc[-1]
    price_data = {
        "open": int(latest["open"]),
        "close": int(latest["close"]),
        "low": int(latest["low"]),
        "high": int(latest["high"]),
        "volume": int(latest["volume"]),
        "bar_date": _bar_date(df),
    }
    change_data = _price_change(df)

    try:
        macd_1d = indicators.macd_cross_signal(df)
        rsi_1d = indicators.rsi_zone_signal(df)
        rsi_value_1d = indicators.rsi_latest_value(df)
        bb = indicators.bollinger(df)
        bb_upper = bb.get("bb_upper")
        bb_mid = bb.get("bb_mid")
        bb_lower = bb.get("bb_lower")
    except Exception as e:
        logger.warning(f"[KIS] 1일봉 지표 계산 실패 ({code}): {e}")
        macd_1d = rsi_1d = None
        rsi_value_1d = None
        bb_upper = bb_mid = bb_lower = None

    df60 = _yf_intraday_60m(code)
    if df60 is not None:
        try:
            macd_60m = indicators.macd_cross_signal(df60)
            rsi_60m = indicators.rsi_zone_signal(df60)
            rsi_value_60m = indicators.rsi_latest_value(df60)
        except Exception as e:
            logger.warning(f"[KIS] 60분봉 지표 계산 실패 ({code}): {e}")
            macd_60m = rsi_60m = None
            rsi_value_60m = None
    else:
        macd_60m = rsi_60m = None
        rsi_value_60m = None

    indicator_data = {
        "macd_1d": macd_1d, "rsi_1d": rsi_1d,
        "macd_60m": macd_60m, "rsi_60m": rsi_60m,
        "rsi_value_1d": rsi_value_1d, "rsi_value_60m": rsi_value_60m,
        "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
    }

    time.sleep(KIS_RATE_LIMIT_DELAY)
    ratio_data = _kis_financial_ratio(code, token)

    time.sleep(KIS_RATE_LIMIT_DELAY)
    income_data = _kis_income_statement(code, token)

    view_data = {
        "short_view": indicators.short_term_view(macd_60m, rsi_60m),
        "long_view": indicators.long_term_view(
            macd_1d, rsi_1d, ratio_data["per"], ratio_data["pbr"], ratio_data["roe"]
        ),
        "short_score": indicators.short_term_score(macd_60m, rsi_60m),
        "long_score": indicators.long_term_score(
            macd_1d, rsi_1d, ratio_data["per"], ratio_data["pbr"], ratio_data["roe"]
        ),
    }

    return {"code": code, "name": name, **price_data, **change_data, **indicator_data,
            **view_data, **ratio_data, **income_data,
            "source": "kis", "source_60m": ("yfinance" if df60 is not None else None),
            "error": None}


# ────────────────────────────────────────────
# Yahoo Finance 폴백
# ────────────────────────────────────────────

# code → 확정된 접미사(".KS"/".KQ") 캐시. 한 번 해석하면 이후 프로브를 생략해
# Yahoo 왕복 횟수(및 429 스로틀)를 줄인다.
_YF_SUFFIX_CACHE: dict[str, str] = {}
_YF_SUFFIX_LOCK = threading.Lock()


def _yf_ticker(code: str) -> yf.Ticker | None:
    """코스피(.KS) 먼저 시도, 실패하면 코스닥(.KQ). 확정 접미사는 캐싱해 재프로브 회피."""
    with _YF_SUFFIX_LOCK:
        cached = _YF_SUFFIX_CACHE.get(code)
    if cached is not None:
        return yf.Ticker(f"{code}{cached}")

    for suffix in [".KS", ".KQ"]:
        ticker = yf.Ticker(f"{code}{suffix}")
        hist = ticker.history(period="5d")
        if not hist.empty:
            with _YF_SUFFIX_LOCK:
                _YF_SUFFIX_CACHE[code] = suffix
            return ticker
    return None


def fetch_yf_ohlcv(code: str, interval: str, period: str) -> pd.DataFrame | None:
    """Yahoo Finance OHLCV 조회 일반화 (interval/period는 yf Ticker.history() 인자 그대로 전달).

    반환 컬럼: date(문자열: 일봉류는 YYYYMMDD, 분봉류는 YYYYMMDD HHMM)/open/high/low/close/volume.
    인덱스는 원본 tz-aware DatetimeIndex를 그대로 유지한다 — 분봉 tf의 정확한 epoch 계산은
    (문자열 재파싱이 아니라) 이 tz-aware 타임스탬프의 .timestamp() 를 직접 쓰는 편이 안전하다
    (문자열로 한 번 포맷하면 어느 tz 기준 wall-clock인지 재구성 시 오차 위험이 있음).
    실패·빈 데이터 시 None.
    """
    try:
        ticker = _yf_ticker(code)
        if ticker is None:
            return None
        # auto_adjust=True 를 명시해 분할·배당 조정 종가로 통일한다(yfinance 버전별
        # 기본값 차이로 KIS 경로와 조정 기준이 어긋나 수익률이 달라지는 것을 방지).
        hist = ticker.history(period=period, interval=interval, auto_adjust=True)
        if hist is None or hist.empty:
            return None
        hist = hist.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if hist.empty:
            return None
        date_fmt = "%Y%m%d" if interval in ("1d", "1wk", "1mo") else "%Y%m%d%H%M"
        df = pd.DataFrame({
            "date": hist.index.strftime(date_fmt),
            "open": hist["Open"].astype(float),
            "high": hist["High"].astype(float),
            "low": hist["Low"].astype(float),
            "close": hist["Close"].astype(float),
            "volume": hist["Volume"].astype(int),
        })
        df.index = hist.index
        return df
    except Exception as e:
        logger.warning(f"[YF] OHLCV 수집 실패 ({code}, interval={interval}, period={period}): {e}")
        return None


def _yf_intraday_60m(code: str) -> pd.DataFrame | None:
    """기존 호출부(스냅샷 수집 60분봉 지표) 전용 — reset_index 로 기존 RangeIndex 동작 유지."""
    df = fetch_yf_ohlcv(code, interval="60m", period="6mo")
    if df is None:
        return None
    return df.reset_index(drop=True)


def _fetch_from_yfinance(code: str, name: str) -> dict | None:
    """Yahoo Finance로 OHLCV + 기술지표 + 일부 재무 수집. 실패 시 None 반환."""
    logger.info(f"[YF] 폴백 시도 ({code})")
    try:
        ticker = _yf_ticker(code)
        if ticker is None:
            logger.info(f"[YF] ticker 없음 ({code})")
            return None

        hist = ticker.history(period="6mo")
        if hist.empty:
            return None
        hist = hist.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if hist.empty:
            return None

        df = pd.DataFrame({
            "date": hist.index.strftime("%Y%m%d"),
            "open": hist["Open"].astype(int),
            "high": hist["High"].astype(int),
            "low": hist["Low"].astype(int),
            "close": hist["Close"].astype(int),
            "volume": hist["Volume"].astype(int),
        }).reset_index(drop=True)

        latest = df.iloc[-1]
        price_data = {
            "open": int(latest["open"]),
            "close": int(latest["close"]),
            "low": int(latest["low"]),
            "high": int(latest["high"]),
            "volume": int(latest["volume"]),
            "bar_date": _bar_date(df),
        }
        change_data = _price_change(df)

        try:
            macd_1d = indicators.macd_cross_signal(df)
            rsi_1d = indicators.rsi_zone_signal(df)
            rsi_value_1d = indicators.rsi_latest_value(df)
            bb = indicators.bollinger(df)
            bb_upper = bb.get("bb_upper")
            bb_mid = bb.get("bb_mid")
            bb_lower = bb.get("bb_lower")
        except Exception as e:
            logger.warning(f"[YF] 1일봉 지표 계산 실패 ({code}): {e}")
            macd_1d = rsi_1d = None
            rsi_value_1d = None
            bb_upper = bb_mid = bb_lower = None

        df60 = _yf_intraday_60m(code)
        if df60 is not None:
            try:
                macd_60m = indicators.macd_cross_signal(df60)
                rsi_60m = indicators.rsi_zone_signal(df60)
                rsi_value_60m = indicators.rsi_latest_value(df60)
            except Exception as e:
                logger.warning(f"[YF] 60분봉 지표 계산 실패 ({code}): {e}")
                macd_60m = rsi_60m = None
                rsi_value_60m = None
        else:
            macd_60m = rsi_60m = None
            rsi_value_60m = None

        indicator_data = {
            "macd_1d": macd_1d, "rsi_1d": rsi_1d,
            "macd_60m": macd_60m, "rsi_60m": rsi_60m,
            "rsi_value_1d": rsi_value_1d, "rsi_value_60m": rsi_value_60m,
            "bb_upper": bb_upper, "bb_mid": bb_mid, "bb_lower": bb_lower,
        }

        info = ticker.info
        roe_raw = _to_float(info.get("returnOnEquity"))
        ratio_data = {
            "per": _to_float(info.get("trailingPE")),
            "pbr": _to_float(info.get("priceToBook")),
            "roe": round(roe_raw * 100, 2) if roe_raw is not None else None,
        }
        income_data = {
            "revenue": _to_int(info.get("totalRevenue")),
            "net_income": _to_int(info.get("netIncomeToCommon")),
        }

        view_data = {
            "short_view": indicators.short_term_view(macd_60m, rsi_60m),
            "long_view": indicators.long_term_view(
                macd_1d, rsi_1d, ratio_data["per"], ratio_data["pbr"], ratio_data["roe"]
            ),
            "short_score": indicators.short_term_score(macd_60m, rsi_60m),
            "long_score": indicators.long_term_score(
                macd_1d, rsi_1d, ratio_data["per"], ratio_data["pbr"], ratio_data["roe"]
            ),
        }

        logger.info(f"[YF] 수집 성공 ({code})")
        return {"code": code, "name": name, **price_data, **change_data, **indicator_data,
                **view_data, **ratio_data, **income_data,
                "source": "yfinance", "source_60m": ("yfinance" if df60 is not None else None),
                "error": None}

    except Exception as e:
        logger.warning(f"[YF] 수집 실패 ({code}): {e}")
        return None


# ────────────────────────────────────────────
# 공개 인터페이스
# ────────────────────────────────────────────

def fetch_stock_price(code: str, name: str, token: str) -> dict:
    base = {"code": code, "name": name}

    result = _fetch_from_kis(code, name, token)
    if result is not None:
        return result

    result = _fetch_from_yfinance(code, name)
    if result is not None:
        return result

    return {**base, **_EMPTY_RESULT, "error": f"KIS·YF 모두 실패 ({code})"}


def fetch_all(stock_list: list[dict]) -> tuple[list[dict], list[dict]]:
    try:
        token = kis_auth.get_token()
    except Exception as e:
        logger.warning(f"[crawler] KIS 토큰 발급 실패 — 전 종목 Yahoo 폴백으로 진행: {e}")
        token = None

    success_list = []
    failed_list = []

    for item in stock_list:
        result = fetch_stock_price(item["code"], item["name"], token)
        if result["error"] is None:
            success_list.append(result)
        else:
            failed_list.append(result)

    return success_list, failed_list


def fetch_yf_index_ohlcv(ticker: str, interval: str = "1d", period: str = "max") -> pd.DataFrame | None:
    """Yahoo Finance 지수(코스피 등) OHLCV 조회 — fetch_yf_ohlcv 와 별개 함수.

    fetch_yf_ohlcv 는 내부에서 종목코드에 .KS/.KQ 접미사를 붙이는데, "^KS11" 같은 지수
    심볼은 그 규칙 대상이 아니다(붙이면 존재하지 않는 티커가 된다). 원시 ticker 문자열을
    그대로 yf.Ticker 에 넘기는 전용 경로가 필요해 병치한다 — 기존 종목 조회는 무변경.

    반환 스키마는 fetch_yf_ohlcv 와 동일: date(일봉류 YYYYMMDD)/open/high/low/close/volume
    + 원본 tz-aware DatetimeIndex 유지. 실패·빈 데이터 시 None.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        hist = ticker_obj.history(period=period, interval=interval)
        if hist is None or hist.empty:
            return None
        hist = hist.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if hist.empty:
            return None
        date_fmt = "%Y%m%d" if interval in ("1d", "1wk", "1mo") else "%Y%m%d%H%M"
        df = pd.DataFrame({
            "date": hist.index.strftime(date_fmt),
            "open": hist["Open"].astype(float),
            "high": hist["High"].astype(float),
            "low": hist["Low"].astype(float),
            "close": hist["Close"].astype(float),
            "volume": hist["Volume"].astype(int),
        })
        df.index = hist.index
        return df
    except Exception as e:
        logger.warning(f"[YF] 지수 OHLCV 수집 실패 ({ticker}, interval={interval}, period={period}): {e}")
        return None
