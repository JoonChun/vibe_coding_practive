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
    PULLBACK_MA_SHORT, PULLBACK_MA_MID, PULLBACK_MA_LONG, PULLBACK_MA_SLOPE_LOOKBACK,
    PULLBACK_PROXIMITY_PCT, PULLBACK_MAX_DEPTH_PCT, PULLBACK_SWING_HIGH_LOOKBACK,
    PULLBACK_VOL_MA_PERIOD, PULLBACK_VOL_CONTRACTION_RATIO, PULLBACK_VOL_EXPANSION_RATIO,
    PULLBACK_ADX_PERIOD, PULLBACK_ADX_TREND_MIN, PULLBACK_EXIT_PCT, PULLBACK_MIN_BARS,
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


def rsi_latest_value(df: pd.DataFrame) -> float | None:
    """최신 RSI 수치(소수 1자리 반올림). 데이터부족 시 None."""
    if len(df) <= RSI_PERIOD:
        return None
    close = df["close"].astype(float)
    rsi_series = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi()
    if len(rsi_series) == 0 or rsi_series.isna().all():
        return None
    latest = rsi_series.iloc[-1]
    if math.isnan(latest):
        return None
    return round(float(latest), 1)


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


def _is_nan(val) -> bool:
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return True


def pullback_signal(df: pd.DataFrame) -> dict:
    """정배열 추세 + MA20 되돌림(눌림목) 판정. 순수 함수(외부 I/O 없음).

    입력: 일봉 DataFrame(t 오름차순, open/high/low/close/volume 컬럼 필수, 최대 100봉 가정).
    반환: {"status": str, "reason": str, "trend_up": bool, "checks": list[dict]}.

    status 는 정확히 다음 6개 문자열 중 하나(프론트 계약 — 문자열 변경 금지):
      데이터부족 / 추세아님 / 추세지속 / 눌림 진행중(관망) / 눌림목 반등(매수후보) / 눌림 이탈(무효)

    checks 는 프론트 체크리스트용 구조화 항목(순서·label 문자열 고정 — 프론트 계약):
      [정배열(MA5>MA20>MA60, Close>MA60 포함), MA20 기울기 상승, 추세 강도(ADX≥20),
       MA20 근접(눌림 깊이), 거래량 수축(≤60%), 반등 트리거(양봉·전일고가·거래량)]
    각 항목은 status 산정에 쓰는 조건의 독립 상태를 그대로 보여줄 뿐 — 항목끼리 서로
    배타적일 수 있다(예: 거래량 수축과 반등 트리거의 거래량 팽창은 동시에 True일 수 없다).
    "데이터부족" 상태에서는 평가 자체가 불가하므로 checks=[] (빈 리스트).

    판정 순서: 데이터부족 → 추세 필터(추세아님) → 이탈 → 반등 → 진행중 → (그 외) 추세지속.
    """
    if len(df) < PULLBACK_MIN_BARS:
        return {
            "status": "데이터부족",
            "reason": f"유효 봉수 부족({len(df)}<{PULLBACK_MIN_BARS})",
            "trend_up": False,
            "checks": [],
        }

    close = df["close"].astype(float)
    open_ = df["open"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)

    ma_short = close.rolling(PULLBACK_MA_SHORT).mean()
    ma_mid = close.rolling(PULLBACK_MA_MID).mean()
    ma_long = close.rolling(PULLBACK_MA_LONG).mean()
    vol_ma = volume.rolling(PULLBACK_VOL_MA_PERIOD).mean()

    try:
        adx_series = ta.trend.ADXIndicator(
            high=high, low=low, close=close, window=PULLBACK_ADX_PERIOD
        ).adx()
    except Exception:
        adx_series = pd.Series([float("nan")] * len(df))

    slope_lookback_idx = -1 - PULLBACK_MA_SLOPE_LOOKBACK

    curr_close = close.iloc[-1]
    curr_open = open_.iloc[-1]
    prev_high = high.iloc[-2]
    curr_ma_short = ma_short.iloc[-1]
    curr_ma_mid = ma_mid.iloc[-1]
    curr_ma_long = ma_long.iloc[-1]
    prev_ma_mid = (
        ma_mid.iloc[slope_lookback_idx] if len(ma_mid) >= abs(slope_lookback_idx) else float("nan")
    )
    curr_adx = adx_series.iloc[-1] if len(adx_series) else float("nan")
    curr_volume = volume.iloc[-1]
    curr_vol_ma = vol_ma.iloc[-1]

    required = [curr_close, curr_ma_short, curr_ma_mid, curr_ma_long, prev_ma_mid, curr_adx, curr_vol_ma]
    if any(_is_nan(v) for v in required):
        return {"status": "데이터부족", "reason": "지표 계산 불가(NaN)", "trend_up": False, "checks": []}

    aligned = curr_ma_short > curr_ma_mid > curr_ma_long
    above_long = curr_close > curr_ma_long
    slope_up = curr_ma_mid > prev_ma_mid
    adx_ok = curr_adx >= PULLBACK_ADX_TREND_MIN
    trend_up = aligned and above_long and slope_up and adx_ok

    # checks 구성에 필요한 나머지 불리언들 — status 분기(trend_up 여부)와 무관하게
    # 항상 계산해 둔다(추세아님·이탈 상태에서도 checks=[6개]를 온전히 채우기 위함).
    # 이미 위에서 NaN 검증을 마친 curr_vol_ma/curr_ma_mid 등을 그대로 재사용한다.
    proximity_pct = abs(curr_close - curr_ma_mid) / curr_ma_mid * 100
    swing_high = high.iloc[-PULLBACK_SWING_HIGH_LOOKBACK:].max()
    depth_pct = (swing_high - curr_close) / swing_high * 100 if swing_high else float("nan")
    in_proximity = proximity_pct <= PULLBACK_PROXIMITY_PCT
    depth_ok = not _is_nan(depth_pct) and depth_pct <= PULLBACK_MAX_DEPTH_PCT
    vol_ratio = curr_volume / curr_vol_ma if curr_vol_ma else float("nan")

    is_bullish = curr_close > curr_open
    breaks_prev_high = curr_close > prev_high
    vol_expansion = not _is_nan(vol_ratio) and vol_ratio >= PULLBACK_VOL_EXPANSION_RATIO
    vol_contraction = not _is_nan(vol_ratio) and vol_ratio <= PULLBACK_VOL_CONTRACTION_RATIO

    checks = [
        {"label": "정배열 (MA5>MA20>MA60)", "ok": bool(aligned and above_long)},
        {"label": "MA20 기울기 상승", "ok": bool(slope_up)},
        {"label": "추세 강도 (ADX≥20)", "ok": bool(adx_ok)},
        {"label": "MA20 근접 (눌림 깊이)", "ok": bool(in_proximity and depth_ok)},
        {"label": "거래량 수축 (≤60%)", "ok": bool(vol_contraction)},
        {"label": "반등 트리거 (양봉·전일고가·거래량)", "ok": bool(is_bullish and breaks_prev_high and vol_expansion)},
    ]

    if not trend_up:
        reasons = []
        if not aligned:
            reasons.append("정배열 미충족")
        if not above_long:
            reasons.append("MA60 하회")
        if not slope_up:
            reasons.append("MA20 기울기 하락")
        if not adx_ok:
            reasons.append(f"ADX {curr_adx:.1f}<{PULLBACK_ADX_TREND_MIN}")
        return {
            "status": "추세아님",
            "reason": "·".join(reasons) or "추세 필터 미충족",
            "trend_up": False,
            "checks": checks,
        }

    # 이하 trend_up == True 확정 구간
    exit_pct = (curr_ma_mid - curr_close) / curr_ma_mid * 100  # 양수면 MA20 하회
    if exit_pct > PULLBACK_EXIT_PCT:
        return {
            "status": "눌림 이탈(무효)",
            "reason": f"MA20 대비 {exit_pct:.1f}% 하회(기준 {PULLBACK_EXIT_PCT}%)",
            "trend_up": True,
            "checks": checks,
        }

    if in_proximity and depth_ok and is_bullish and breaks_prev_high and vol_expansion:
        return {
            "status": "눌림목 반등(매수후보)",
            "reason": f"양봉·전일고가 돌파·거래량 {vol_ratio * 100:.0f}%",
            "trend_up": True,
            "checks": checks,
        }

    if in_proximity and depth_ok and vol_contraction:
        return {
            "status": "눌림 진행중(관망)",
            "reason": f"MA20 근접 {proximity_pct:.1f}%·거래량 {vol_ratio * 100:.0f}%로 수축",
            "trend_up": True,
            "checks": checks,
        }

    if not in_proximity:
        reason = f"MA20 이격 {proximity_pct:.1f}%(근접밴드 {PULLBACK_PROXIMITY_PCT}% 밖)"
    elif not depth_ok:
        reason = f"전고점 대비 낙폭 {depth_pct:.1f}%(눌림 범위 {PULLBACK_MAX_DEPTH_PCT}% 초과)"
    else:
        reason = f"MA20 근접이나 거래량 {vol_ratio * 100:.0f}%(수축·팽창 기준 미충족)"
    return {"status": "추세지속", "reason": reason, "trend_up": True, "checks": checks}


_NO_DATA = (None, "데이터부족")


def _macd_score(sig) -> int:
    return {
        "골든크로스(진입)": 2,
        "진입구간": 1,
        "매도구간": -1,
        "데드크로스(매도)": -2,
    }.get(sig, 0)


def _rsi_score(sig, trend_up: bool = False) -> int:
    # 추세장(trend_up=True)에서는 RSI 과매수가 장기간 유지되는 경우가 흔해(정배열 지속),
    # 역추세 매도 신호로 오인하지 않도록 감점을 무효화한다(0). short(60m) 호출부는
    # trend_up 기본값(False)을 그대로 사용해 기존 동작을 100% 보존한다.
    if sig == "과매수(매도)" and trend_up:
        return 0
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


def long_term_view(macd_1d, rsi_1d, per, pbr, roe, trend_up: bool = False) -> str:
    fund = _fundamental_score(per, pbr, roe)
    if macd_1d in _NO_DATA and rsi_1d in _NO_DATA and fund == 0:
        return "데이터부족"
    tech = _macd_score(macd_1d) + _rsi_score(rsi_1d, trend_up)
    return _level5(tech + fund, strong=3)


def short_term_score(macd_60m, rsi_60m) -> int | None:
    """단기(60분봉) 스코어 합. 임계값은 ±2 (short_term_view 와 동일 기준)."""
    if macd_60m in _NO_DATA and rsi_60m in _NO_DATA:
        return None
    return _macd_score(macd_60m) + _rsi_score(rsi_60m)


def long_term_score(macd_1d, rsi_1d, per, pbr, roe, trend_up: bool = False) -> int | None:
    """장기(일봉+재무) 스코어 합. 임계값은 ±3 (long_term_view 와 동일 기준)."""
    fund = _fundamental_score(per, pbr, roe)
    if macd_1d in _NO_DATA and rsi_1d in _NO_DATA and fund == 0:
        return None
    tech = _macd_score(macd_1d) + _rsi_score(rsi_1d, trend_up)
    return tech + fund
