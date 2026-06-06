import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import ta.momentum
import ta.trend
import ta.volatility

from config import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STD, RSI_OVERSOLD, RSI_OVERBOUGHT,
)


def _to_float(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


_MIN_BARS_MACD = MACD_SLOW + MACD_SIGNAL


def macd_cross_signal(df: pd.DataFrame) -> str:
    if len(df) < _MIN_BARS_MACD:
        return "데이터부족"
    close = df["close"].astype(float)
    macd_obj = ta.trend.MACD(
        close=close,
        window_fast=MACD_FAST,
        window_slow=MACD_SLOW,
        window_sign=MACD_SIGNAL,
    )
    macd_line = macd_obj.macd()
    signal_line = macd_obj.macd_signal()
    prev_m, curr_m = macd_line.iloc[-2], macd_line.iloc[-1]
    prev_s, curr_s = signal_line.iloc[-2], signal_line.iloc[-1]
    if any(math.isnan(v) for v in [prev_m, curr_m, prev_s, curr_s]):
        return "데이터부족"
    if prev_m <= prev_s and curr_m > curr_s:
        return "골든크로스(진입)"
    if prev_m >= prev_s and curr_m < curr_s:
        return "데드크로스(매도)"
    if curr_m > curr_s:
        return "진입구간"
    return "매도구간"


def rsi_zone_signal(df: pd.DataFrame) -> str:
    if len(df) <= RSI_PERIOD:
        return "데이터부족"
    close = df["close"].astype(float)
    rsi_series = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi()
    if len(rsi_series) == 0 or rsi_series.isna().all():
        return "데이터부족"
    latest = rsi_series.iloc[-1]
    if math.isnan(latest):
        return "데이터부족"
    if latest <= RSI_OVERSOLD:
        return "과매도(진입)"
    if latest >= RSI_OVERBOUGHT:
        return "과매수(매도)"
    return "중립"


def bollinger(df: pd.DataFrame) -> dict:
    close = df["close"].astype(float)
    bb_obj = ta.volatility.BollingerBands(
        close=close,
        window=BB_PERIOD,
        window_dev=BB_STD,
    )
    return {
        "bb_upper": _to_float(bb_obj.bollinger_hband().iloc[-1]),
        "bb_mid":   _to_float(bb_obj.bollinger_mavg().iloc[-1]),
        "bb_lower": _to_float(bb_obj.bollinger_lband().iloc[-1]),
    }


_NO_DATA = (None, "데이터부족")


def _macd_score(sig) -> int:
    return {
        "골든크로스(진입)": 2,
        "진입구간": 1,
        "매도구간": -1,
        "데드크로스(매도)": -2,
    }.get(sig, 0)


def _rsi_score(sig) -> int:
    return {
        "과매도(진입)": 1,
        "과매수(매도)": -1,
    }.get(sig, 0)


def _fundamental_score(per, pbr, roe) -> int:
    score = 0
    if per is not None:
        if per <= 0:
            score -= 1
        elif per < 10:
            score += 1
        elif per >= 30:
            score -= 1
    if pbr is not None and pbr > 0:
        if pbr < 1:
            score += 1
        elif pbr >= 3:
            score -= 1
    if roe is not None:
        if roe >= 15:
            score += 1
        elif roe < 0:
            score -= 1
    return score


def _level5(score: int, strong: int) -> str:
    if score >= strong:
        return "강력매수"
    if score >= 1:
        return "매수"
    if score <= -strong:
        return "강력매도"
    if score <= -1:
        return "매도"
    return "관망"


def short_term_view(macd_60m, rsi_60m) -> str:
    if macd_60m in _NO_DATA and rsi_60m in _NO_DATA:
        return "데이터부족"
    return _level5(_macd_score(macd_60m) + _rsi_score(rsi_60m), strong=2)


def long_term_view(macd_1d, rsi_1d, per, pbr, roe) -> str:
    fund = _fundamental_score(per, pbr, roe)
    if macd_1d in _NO_DATA and rsi_1d in _NO_DATA and fund == 0:
        return "데이터부족"
    tech = _macd_score(macd_1d) + _rsi_score(rsi_1d)
    return _level5(tech + fund, strong=3)
