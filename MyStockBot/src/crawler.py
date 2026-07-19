import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import pandas as pd
import yfinance as yf

from config import (
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_DAILY_PRICE_URL,
    KIS_FINANCIAL_RATIO_URL,
    KIS_INCOME_STMT_URL,
    KIS_MINUTE_PRICE_URL,
    KIS_RATE_LIMIT_DELAY,
    OHLCV_LOOKBACK_DAYS,
    TIMEZONE,
)
import indicators
import kis_auth


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


_EMPTY_RESULT = {
    "open": None, "close": None, "low": None, "high": None, "volume": None,
    "change": None, "change_pct": None,
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
    from zoneinfo import ZoneInfo
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
        resp = requests.get(KIS_DAILY_PRICE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[KIS] OHLCV 요청 실패 ({code}, period={period}): {e}")
        return None

    output2 = data.get("output2")
    if not output2:
        print(f"[KIS] OHLCV output2 없음 ({code}, period={period}): rt_cd={data.get('rt_cd')} msg={data.get('msg1')}")
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


# 페이지네이션 시 다음 호출의 [start, end] 구간을 얼마나 잡을지(일수) — period별 근사치.
# 각 tf의 실제 발생 빈도(거래일/거래주/거래월)를 감안해 한 호출이 대략 100건 근처로
# 나오도록 여유를 둔 상수(공휴일 등으로 거래일수가 적은 만큼 살짝 넉넉하게 잡음).
_PAGE_WINDOW_DAYS = {"D": 140, "W": 700, "M": 3000}


def fetch_kis_ohlcv_paged(
    code: str,
    token: str,
    period: str,
    target_count: int,
    max_pages: int = 15,
) -> pd.DataFrame | None:
    """KIS 기간별시세(FHKST03010100·inquire-daily-itemchartprice)를 날짜 구간을 과거로
    옮겨가며 반복 호출해 최대 target_count건까지 누적한다.

    이 TR/URL은 fetch_kis_ohlcv(단일 호출, 무변경)와 완전히 동일하다 — KIS 공식 스펙상
    호출당 최대 100건 제한이 있어, 장기 이력(연봉 다건 등)을 한 번에 못 받는 문제를
    페이지네이션으로 해결한다. (참고: 이 함수를 만들며 "당일분봉 TR이 FHKST03010200"
    이라는 사실도 별도로 공식 확인했다 — 즉 FHKST03010200은 분봉 전용 TR이며, 일봉
    페이지네이션에는 기존 fetch_kis_ohlcv와 동일하게 FHKST03010100을 그대로 재사용하는
    것이 맞다. 자세한 분봉 TR 출처는 fetch_kis_minutes() 상단 주석 참조.)

    페이지네이션 규칙:
      - 첫 호출: end=오늘, start=end-윈도우(period별 _PAGE_WINDOW_DAYS).
      - 다음 호출: end=(직전 응답의 가장 이른 날짜 - 1일), start=end-윈도우.
      - 응답이 비거나(더 과거 데이터 없음) 새로 얻은 가장 이른 날짜가 이전 페이지보다
        더 과거로 진행하지 못하면(같은 구간 반복 등 이상 상황) 중단한다.
      - target_count건 이상 모이면 즉시 중단, max_pages 도달 시에도 중단(폭주 방지 상한
        — 반드시 준수).
      - 페이지 호출 사이 KIS_RATE_LIMIT_DELAY sleep(다음 페이지를 실제로 호출할 때만).

    반환: fetch_kis_ohlcv와 동일 스키마(date 'YYYYMMDD'/open/high/low/close/volume),
    날짜 오름차순, 중복 날짜 제거. target_count 초과분은 최신 target_count건만 남긴다
    (오름차순 유지). 실패·빈 데이터 시 None.
    """
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(TIMEZONE)
    end = datetime.now(tz)
    window_days = _PAGE_WINDOW_DAYS.get(period, _PAGE_WINDOW_DAYS["D"])

    all_rows: dict[str, dict] = {}
    earliest_seen: str | None = None

    for page in range(max_pages):
        start = end - timedelta(days=window_days)

        headers = _get_headers(token)
        headers["tr_id"] = "FHKST03010100"
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
            "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",
        }
        try:
            resp = requests.get(KIS_DAILY_PRICE_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[KIS] OHLCV 페이지네이션 요청 실패 ({code}, period={period}, page={page}): {e}")
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
            end = datetime.strptime(new_earliest, "%Y%m%d").replace(tzinfo=tz) - timedelta(days=1)
        except ValueError:
            break

        time.sleep(KIS_RATE_LIMIT_DELAY)

    if not all_rows:
        return None

    df = pd.DataFrame(list(all_rows.values())).sort_values("date").reset_index(drop=True)
    if len(df) > target_count:
        df = df.iloc[-target_count:].reset_index(drop=True)
    return df


def fetch_kis_minutes(code: str, token: str, max_pages: int = 15) -> pd.DataFrame | None:
    """KIS 주식당일분봉조회(당일 1분봉)를 시간 역방향으로 최대 max_pages 페이지(페이지당
    최대 30건) 모아 반환한다.

    max_pages 기본 15: 페이지당 30분 × 15 = 450분 > 정규장 390분(09:00~15:30)이라
    하루 전체 분봉을 한 사이클에 커버한다(의원 검수 지적 반영 — 8페이지=240분은 후반
    시간대가 잘렸음).

    ────────────────────────────────────────────────────────────────────────
    출처(WebFetch로 공식 확인, 추측 아님):
      URL·TR ID·요청 파라미터·페이지당 최대 건수·FID_INPUT_HOUR_1 의미 — 아래 공식 예제
      원문 그대로 이식(2026-07 조회):
      https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/
      examples_llm/domestic_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py
        - API_URL = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        - tr_id = "FHKST03010200" (실전/모의 동일)
        - params: FID_COND_MRKT_DIV_CODE("J"=KRX), FID_INPUT_ISCD(종목코드),
          FID_INPUT_HOUR_1(조회기준시각 HHMMSS — "미래일시 입력 시 현재가로 조회됨"이
          원문 docstring에 명시됨), FID_PW_DATA_INCU_YN("Y"=과거데이터포함 — 이 값이
          "N"이면 과거 데이터가 안 실려 페이지네이션이 불가능해지므로 항상 "Y" 고정),
          FID_ETC_CLS_CODE("")
        - "실전계좌/모의계좌의 경우, 한 번의 호출에 최대 30건까지 확인 가능" (원문 docstring)
        - "당일 분봉 데이터만 제공됩니다(전일자 분봉 미제공)" (원문 docstring)
      output2 필드명 — 공식 예제 파일 자체는 pd.DataFrame(res.getBody().output2)로 KIS가
      내려주는 raw JSON 키를 그대로 통과시켜 컬럼명을 하드코딩하지 않는다(동적 패스스루).
      이 레포 안에서 이미 공식 확인된 동일 계열 필드명(일봉 REST — crawler.fetch_kis_ohlcv:
      stck_bsop_date/stck_oprc/stck_hgpr/stck_lwpr/stck_clpr/acml_vol, 실시간체결 WS —
      server/services/kis_ws.py 상단 H0STCNT0 필드표: STCK_CNTG_HOUR/CNTG_VOL 등)와 동일
      명명 규칙이며, 커뮤니티 교차검증(inflearn.com/community/questions/1606220 — "국내주식
      과거 분봉데이터 관련" 질문의 답변이 output2 필드로 stck_cntg_hour/stck_prpr/stck_oprc/
      stck_hgpr/stck_lwpr/cntg_vol 을 명시하고, 페이지네이션도 "마지막 stck_cntg_hour를
      다음 FID_INPUT_HOUR_1로 교체해 while 반복 호출"이라 설명 — 아래 구현과 일치)로
      확인한 필드명을 사용한다:
        stck_bsop_date(영업일자), stck_cntg_hour(체결시각 HHMMSS),
        stck_prpr(체결 시점 현재가 — 해당 분봉 종가로 사용),
        stck_oprc/stck_hgpr/stck_lwpr(시가/고가/저가), cntg_vol(해당 분 체결거래량).
      실제 응답 필드가 위 명명과 다를 가능성에 대비해 각 행 파싱은 KeyError/ValueError를
      개별 삼켜 스킵한다(기존 fetch_kis_ohlcv와 동일 관례) — 전량 스킵되면 빈 결과로
      처리되어 호출부가 자연히 yfinance 폴백으로 넘어간다.
    ────────────────────────────────────────────────────────────────────────

    페이지네이션: 첫 호출 FID_INPUT_HOUR_1=현재시각(HHMMSS). 이후 호출은 직전 페이지의
    가장 이른 체결시각에서 1분을 뺀 값을 다음 FID_INPUT_HOUR_1로 사용(경계 분봉 중복 재조회
    방지). 응답이 비거나 더 과거로 진행 못하면 중단. max_pages 상한 반드시 준수. 페이지
    호출 사이 KIS_RATE_LIMIT_DELAY sleep(다음 페이지를 실제로 호출할 때만).

    반환 컬럼: date('YYYYMMDDHHMM' 문자열, 초 단위 절삭)/open/high/low/close/volume,
    시간 오름차순, (영업일자,체결시각) 중복 제거. 장 시작 전·휴장이면 첫 페이지부터 빈
    응답 → None(정상, 폴백 대상). 실패 시에도 None.
    """
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(TIMEZONE)
    now = datetime.now(tz)
    today_str = now.strftime("%Y%m%d")

    headers = _get_headers(token)
    headers["tr_id"] = "FHKST03010200"

    hour_cursor = now.strftime("%H%M%S")
    rows: dict[tuple[str, str], dict] = {}

    for page in range(max_pages):
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_HOUR_1": hour_cursor,
            "FID_PW_DATA_INCU_YN": "Y",
            "FID_ETC_CLS_CODE": "",
        }
        try:
            resp = requests.get(KIS_MINUTE_PRICE_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[KIS] 분봉 요청 실패 ({code}, page={page}): {e}")
            break

        output2 = data.get("output2")
        if not output2:
            break

        page_hours = []
        for item in output2:
            hour = item.get("stck_cntg_hour")
            if not hour:
                continue
            page_hours.append(hour)
            bsop = item.get("stck_bsop_date") or today_str
            key = (bsop, hour)
            if key in rows:
                continue
            try:
                rows[key] = {
                    "date": f"{bsop}{hour[:4]}",
                    "open": int(item["stck_oprc"]),
                    "high": int(item["stck_hgpr"]),
                    "low": int(item["stck_lwpr"]),
                    "close": int(item["stck_prpr"]),
                    "volume": int(item["cntg_vol"]),
                }
            except (KeyError, ValueError):
                continue

        if not page_hours:
            break

        earliest_hour = min(page_hours)
        try:
            prev_dt = datetime.strptime(earliest_hour[:6].ljust(6, "0"), "%H%M%S") - timedelta(minutes=1)
        except ValueError:
            break
        new_cursor = prev_dt.strftime("%H%M%S")

        if new_cursor >= hour_cursor:
            break  # 더 과거로 진행 못함 — 무한루프 방지
        hour_cursor = new_cursor

        time.sleep(KIS_RATE_LIMIT_DELAY)

    if not rows:
        return None

    df = pd.DataFrame(list(rows.values())).sort_values("date")
    # 방어적 중복 제거: dict 키는 (bsop_date,정확한 HHMMSS) 단위라 초 단위까지 다르면 별개
    # 항목으로 남을 수 있으나, 최종 date 문자열은 분(HHMM) 단위로 절삭하므로 혹시라도 같은
    # 분에 두 레코드가 잡히면 여기서 한 번 더 걸러 분당 1행만 남긴다.
    df = df.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
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
        resp = requests.get(KIS_FINANCIAL_RATIO_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[KIS] 재무비율 요청 실패 ({code}): {e}")
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
        resp = requests.get(KIS_INCOME_STMT_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[KIS] 손익계산서 요청 실패 ({code}): {e}")
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
        print(f"[KIS] 1일봉 지표 계산 실패 ({code}): {e}")
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
            print(f"[KIS] 60분봉 지표 계산 실패 ({code}): {e}")
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

def _yf_ticker(code: str) -> yf.Ticker | None:
    """코스피(.KS) 먼저 시도, 실패하면 코스닥(.KQ)."""
    for suffix in [".KS", ".KQ"]:
        ticker = yf.Ticker(f"{code}{suffix}")
        hist = ticker.history(period="5d")
        if not hist.empty:
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
        hist = ticker.history(period=period, interval=interval)
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
        print(f"[YF] OHLCV 수집 실패 ({code}, interval={interval}, period={period}): {e}")
        return None


def fetch_yf_index_ohlcv(ticker: str, interval: str = "1d", period: str = "max") -> pd.DataFrame | None:
    """Yahoo Finance 지수(코스피 등) OHLCV 조회 — fetch_yf_ohlcv와 별개 함수.

    fetch_yf_ohlcv는 내부에서 _yf_ticker()를 거쳐 종목코드에 .KS/.KQ 접미사를 붙이는데,
    "^KS11" 같은 지수 심볼은 이 접미사 규칙 대상이 아니라(붙이면 존재하지 않는 티커가 됨)
    원시 ticker 문자열을 그대로 yf.Ticker에 전달하는 전용 경로가 필요하다. fetch_yf_ohlcv
    본체는 그대로 두고(기존 종목 조회 무변경) 별도로 병치한다.

    반환 스키마는 fetch_yf_ohlcv와 동일: date(일봉류 YYYYMMDD/분봉류 YYYYMMDDHHMM)/
    open/high/low/close/volume 컬럼 + 원본 tz-aware DatetimeIndex 유지. 실패·빈 데이터 시 None.
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
        print(f"[YF] 지수 OHLCV 수집 실패 ({ticker}, interval={interval}, period={period}): {e}")
        return None


def _yf_intraday_60m(code: str) -> pd.DataFrame | None:
    """기존 호출부(스냅샷 수집 60분봉 지표) 전용 — reset_index 로 기존 RangeIndex 동작 유지."""
    df = fetch_yf_ohlcv(code, interval="60m", period="6mo")
    if df is None:
        return None
    return df.reset_index(drop=True)


def _fetch_from_yfinance(code: str, name: str) -> dict | None:
    """Yahoo Finance로 OHLCV + 기술지표 + 일부 재무 수집. 실패 시 None 반환."""
    print(f"[YF] 폴백 시도 ({code})")
    try:
        ticker = _yf_ticker(code)
        if ticker is None:
            print(f"[YF] ticker 없음 ({code})")
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
            print(f"[YF] 1일봉 지표 계산 실패 ({code}): {e}")
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
                print(f"[YF] 60분봉 지표 계산 실패 ({code}): {e}")
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

        print(f"[YF] 수집 성공 ({code})")
        return {"code": code, "name": name, **price_data, **change_data, **indicator_data,
                **view_data, **ratio_data, **income_data,
                "source": "yfinance", "source_60m": ("yfinance" if df60 is not None else None),
                "error": None}

    except Exception as e:
        print(f"[YF] 수집 실패 ({code}): {e}")
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
        print(f"[crawler] KIS 토큰 발급 실패 — 전 종목 Yahoo 폴백으로 진행: {e}")
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
