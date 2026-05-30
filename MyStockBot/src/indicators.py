import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import ta.momentum
import ta.trend
import ta.volatility

from config import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL, BB_PERIOD, BB_STD


def _to_float(val) -> float | None:
    try:
        f = float(val)
        return None if math.isnan(f) else round(f, 2)
    except (TypeError, ValueError):
        return None


def calculate_indicators(df: pd.DataFrame) -> dict:
    close = df["close"].astype(float)

    rsi = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi()

    macd_obj = ta.trend.MACD(
        close=close,
        window_fast=MACD_FAST,
        window_slow=MACD_SLOW,
        window_sign=MACD_SIGNAL,
    )

    bb_obj = ta.volatility.BollingerBands(
        close=close,
        window=BB_PERIOD,
        window_dev=BB_STD,
    )

    return {
        "rsi":         _to_float(rsi.iloc[-1]),
        "macd":        _to_float(macd_obj.macd().iloc[-1]),
        "macd_signal": _to_float(macd_obj.macd_signal().iloc[-1]),
        "macd_hist":   _to_float(macd_obj.macd_diff().iloc[-1]),
        "bb_upper":    _to_float(bb_obj.bollinger_hband().iloc[-1]),
        "bb_mid":      _to_float(bb_obj.bollinger_mavg().iloc[-1]),
        "bb_lower":    _to_float(bb_obj.bollinger_lband().iloc[-1]),
    }
