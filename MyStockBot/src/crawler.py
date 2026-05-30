import math
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import pandas as pd

from config import (
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    KIS_DAILY_PRICE_URL,
    KIS_FINANCIAL_RATIO_URL,
    KIS_INCOME_STMT_URL,
    KIS_RATE_LIMIT_DELAY,
    OHLCV_LOOKBACK_DAYS,
    TIMEZONE,
)
import indicators
import kis_auth


def _get_headers(token: str) -> dict:
    return {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": os.environ.get(KIS_APP_KEY_ENV, ""),
        "appsecret": os.environ.get(KIS_APP_SECRET_ENV, ""),
    }


def _fetch_daily_ohlcv(code: str, token: str) -> pd.DataFrame | None:
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz)
    lookback = int(OHLCV_LOOKBACK_DAYS * 1.6)
    start = today - timedelta(days=lookback)

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    headers = _get_headers(token)
    headers["tr_id"] = "FHKST01010100"

    try:
        resp = requests.get(
            KIS_DAILY_PRICE_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[crawler] _fetch_daily_ohlcv 요청 실패 ({code}): {e}")
        return None

    output2 = data.get("output2")
    if not output2:
        print(f"[crawler] _fetch_daily_ohlcv output2 없음 ({code}): rt_cd={data.get('rt_cd')} msg={data.get('msg1')}")
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
    df = df.sort_values("date").reset_index(drop=True)
    return df


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


def _fetch_financial_ratio(code: str, token: str) -> dict:
    headers = _get_headers(token)
    headers["tr_id"] = "FHKST66430200"

    params = {
        "FID_DIV_CLS_CODE": "0",
        "fid_input_iscd": code,
        "fid_cond_mrkt_div_code": "J",
    }

    try:
        resp = requests.get(
            KIS_FINANCIAL_RATIO_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[crawler] _fetch_financial_ratio 요청 실패 ({code}): {e}")
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


def _fetch_income_statement(code: str, token: str) -> dict:
    headers = _get_headers(token)
    headers["tr_id"] = "FHKST66430300"

    params = {
        "FID_DIV_CLS_CODE": "0",
        "fid_input_iscd": code,
        "fid_cond_mrkt_div_code": "J",
    }

    try:
        resp = requests.get(
            KIS_INCOME_STMT_URL,
            headers=headers,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[crawler] _fetch_income_statement 요청 실패 ({code}): {e}")
        return {"revenue": None, "net_income": None}

    output = data.get("output")
    if not output:
        return {"revenue": None, "net_income": None}

    item = output[0]
    return {
        "revenue": _to_int(item.get("sale_account")),
        "net_income": _to_int(item.get("thtr_ntin")),
    }


_EMPTY_RESULT = {
    "open": None, "close": None, "low": None, "high": None, "volume": None,
    "rsi": None, "macd": None, "macd_signal": None, "macd_hist": None,
    "bb_upper": None, "bb_mid": None, "bb_lower": None,
    "per": None, "pbr": None, "roe": None,
    "revenue": None, "net_income": None,
}


def fetch_stock_price(code: str, name: str, token: str) -> dict:
    base = {"code": code, "name": name}

    df = _fetch_daily_ohlcv(code, token)
    if df is None or df.empty:
        return {**base, **_EMPTY_RESULT, "error": f"OHLCV 데이터 없음 ({code})"}

    time.sleep(KIS_RATE_LIMIT_DELAY)

    latest = df.iloc[-1]
    price_data = {
        "open": int(latest["open"]),
        "close": int(latest["close"]),
        "low": int(latest["low"]),
        "high": int(latest["high"]),
        "volume": int(latest["volume"]),
    }

    try:
        indicator_data = indicators.calculate_indicators(df)
    except Exception as e:
        print(f"[crawler] indicators 계산 실패 ({code}): {e}")
        indicator_data = {
            "rsi": None, "macd": None, "macd_signal": None, "macd_hist": None,
            "bb_upper": None, "bb_mid": None, "bb_lower": None,
        }

    time.sleep(KIS_RATE_LIMIT_DELAY)

    ratio_data = _fetch_financial_ratio(code, token)

    time.sleep(KIS_RATE_LIMIT_DELAY)

    income_data = _fetch_income_statement(code, token)

    return {
        **base,
        **price_data,
        **indicator_data,
        **ratio_data,
        **income_data,
        "error": None,
    }


def fetch_all(stock_list: list[dict]) -> tuple[list[dict], list[dict]]:
    token = kis_auth.get_token()

    success_list = []
    failed_list = []

    for item in stock_list:
        result = fetch_stock_price(item["code"], item["name"], token)
        if result["error"] is None:
            success_list.append(result)
        else:
            failed_list.append(result)

    return success_list, failed_list
