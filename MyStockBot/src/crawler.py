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


_EMPTY_RESULT = {
    "open": None, "close": None, "low": None, "high": None, "volume": None,
    "macd_1d": None, "rsi_1d": None, "macd_60m": None, "rsi_60m": None,
    "short_view": None, "long_view": None,
    "bb_upper": None, "bb_mid": None, "bb_lower": None,
    "per": None, "pbr": None, "roe": None,
    "revenue": None, "net_income": None,
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


def _kis_daily_ohlcv(code: str, token: str) -> pd.DataFrame | None:
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(TIMEZONE)
    today = datetime.now(tz)
    lookback = int(OHLCV_LOOKBACK_DAYS * 1.6)
    start = today - timedelta(days=lookback)

    headers = _get_headers(token)
    headers["tr_id"] = "FHKST03010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
        "FID_INPUT_DATE_2": today.strftime("%Y%m%d"),
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "0",
    }
    try:
        resp = requests.get(KIS_DAILY_PRICE_URL, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[KIS] OHLCV 요청 실패 ({code}): {e}")
        return None

    output2 = data.get("output2")
    if not output2:
        print(f"[KIS] OHLCV output2 없음 ({code}): rt_cd={data.get('rt_cd')} msg={data.get('msg1')}")
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

    try:
        macd_1d = indicators.macd_cross_signal(df)
        rsi_1d = indicators.rsi_zone_signal(df)
        bb = indicators.bollinger(df)
        bb_upper = bb.get("bb_upper")
        bb_mid = bb.get("bb_mid")
        bb_lower = bb.get("bb_lower")
    except Exception as e:
        print(f"[KIS] 1일봉 지표 계산 실패 ({code}): {e}")
        macd_1d = rsi_1d = None
        bb_upper = bb_mid = bb_lower = None

    df60 = _yf_intraday_60m(code)
    if df60 is not None:
        try:
            macd_60m = indicators.macd_cross_signal(df60)
            rsi_60m = indicators.rsi_zone_signal(df60)
        except Exception as e:
            print(f"[KIS] 60분봉 지표 계산 실패 ({code}): {e}")
            macd_60m = rsi_60m = None
    else:
        macd_60m = rsi_60m = None

    indicator_data = {
        "macd_1d": macd_1d, "rsi_1d": rsi_1d,
        "macd_60m": macd_60m, "rsi_60m": rsi_60m,
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
    }

    return {"code": code, "name": name, **price_data, **indicator_data,
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


def _yf_intraday_60m(code: str) -> pd.DataFrame | None:
    try:
        ticker = _yf_ticker(code)
        if ticker is None:
            return None
        hist = ticker.history(period="6mo", interval="60m")
        if hist is None or hist.empty:
            return None
        hist = hist.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
        if hist.empty:
            return None
        df = pd.DataFrame({
            "date": hist.index.strftime("%Y%m%d%H%M"),
            "open": hist["Open"].astype(float),
            "high": hist["High"].astype(float),
            "low": hist["Low"].astype(float),
            "close": hist["Close"].astype(float),
            "volume": hist["Volume"].astype(int),
        }).reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[YF] 60분봉 수집 실패 ({code}): {e}")
        return None


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

        try:
            macd_1d = indicators.macd_cross_signal(df)
            rsi_1d = indicators.rsi_zone_signal(df)
            bb = indicators.bollinger(df)
            bb_upper = bb.get("bb_upper")
            bb_mid = bb.get("bb_mid")
            bb_lower = bb.get("bb_lower")
        except Exception as e:
            print(f"[YF] 1일봉 지표 계산 실패 ({code}): {e}")
            macd_1d = rsi_1d = None
            bb_upper = bb_mid = bb_lower = None

        df60 = _yf_intraday_60m(code)
        if df60 is not None:
            try:
                macd_60m = indicators.macd_cross_signal(df60)
                rsi_60m = indicators.rsi_zone_signal(df60)
            except Exception as e:
                print(f"[YF] 60분봉 지표 계산 실패 ({code}): {e}")
                macd_60m = rsi_60m = None
        else:
            macd_60m = rsi_60m = None

        indicator_data = {
            "macd_1d": macd_1d, "rsi_1d": rsi_1d,
            "macd_60m": macd_60m, "rsi_60m": rsi_60m,
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
        }

        print(f"[YF] 수집 성공 ({code})")
        return {"code": code, "name": name, **price_data, **indicator_data,
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
