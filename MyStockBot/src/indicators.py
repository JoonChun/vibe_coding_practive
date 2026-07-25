import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import ta.momentum
import ta.trend
import ta.volatility

import decision_rules as rules
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


def macd_label_from_pair(prev_macd, curr_macd, prev_signal, curr_signal) -> str:
    """MACD/시그널 두 시점 값 → 라벨. 순수 함수 — 백테스트가 시계열 1회 계산 후 재사용한다.

    라벨 규칙을 여기 한 곳에만 두어 backtest.py 의 재구현 사본을 없앤다(예전에는 같은 규칙이
    두 곳에 있어, 한쪽만 바꾸면 과거 판정이 조용히 전부 0점=관망이 됐다).
    """
    values = (prev_macd, curr_macd, prev_signal, curr_signal)
    if any(v is None or v != v for v in values):  # NaN != NaN
        return rules.NO_DATA
    if prev_macd <= prev_signal and curr_macd > curr_signal:
        return rules.MACD_GOLDEN_CROSS
    if prev_macd >= prev_signal and curr_macd < curr_signal:
        return rules.MACD_DEAD_CROSS
    return rules.MACD_ABOVE if curr_macd > curr_signal else rules.MACD_BELOW


def rsi_label_from_value(value) -> str:
    """RSI 수치 → 존 라벨. 순수 함수 — 백테스트가 재사용한다."""
    if value is None or value != value:  # NaN
        return rules.NO_DATA
    if value <= RSI_OVERSOLD:
        return rules.RSI_OVERSOLD_ZONE
    if value >= RSI_OVERBOUGHT:
        return rules.RSI_OVERBOUGHT_ZONE
    return rules.RSI_NEUTRAL


def macd_cross_signal(df: pd.DataFrame) -> str:
    if len(df) < _MIN_BARS_MACD:
        return rules.NO_DATA
    close = df["close"].astype(float)
    macd_obj = ta.trend.MACD(
        close=close,
        window_fast=MACD_FAST,
        window_slow=MACD_SLOW,
        window_sign=MACD_SIGNAL,
    )
    macd_line = macd_obj.macd()
    signal_line = macd_obj.macd_signal()
    return macd_label_from_pair(
        macd_line.iloc[-2], macd_line.iloc[-1],
        signal_line.iloc[-2], signal_line.iloc[-1],
    )


def rsi_zone_signal(df: pd.DataFrame) -> str:
    if len(df) <= RSI_PERIOD:
        return rules.NO_DATA
    close = df["close"].astype(float)
    rsi_series = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi()
    if len(rsi_series) == 0 or rsi_series.isna().all():
        return rules.NO_DATA
    return rsi_label_from_value(rsi_series.iloc[-1])


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


_NO_DATA = rules.NO_DATA_INPUTS


def _macd_score(sig, ruleset: rules.RuleSet = rules.BASELINE) -> int:
    return ruleset.macd_score(sig)


def _rsi_score(sig, ruleset: rules.RuleSet = rules.BASELINE) -> int:
    return ruleset.rsi_score(sig)


def _fundamental_score(per, pbr, roe, ruleset: rules.RuleSet = rules.BASELINE) -> int:
    return ruleset.fundamental_score(per, pbr, roe)


def _level5(score: int, strong: int, *, confirm: int | None = None,
            ruleset: rules.RuleSet = rules.BASELINE) -> str:
    return ruleset.level5(score, strong, confirm=confirm)


def short_term_view(macd_60m, rsi_60m, *, ruleset: rules.RuleSet = rules.BASELINE) -> str:
    if macd_60m in _NO_DATA and rsi_60m in _NO_DATA:
        return rules.NO_DATA
    score = ruleset.macd_score(macd_60m) + ruleset.rsi_score(rsi_60m)
    # 단기 점수는 기술 지표만으로 이뤄지므로 별도 확증 요구가 필요 없다(score 가 곧 tech).
    return ruleset.level5(score, ruleset.short_strong)


def long_term_view(macd_1d, rsi_1d, per, pbr, roe, *,
                   ruleset: rules.RuleSet = rules.BASELINE) -> str:
    fund = ruleset.fundamental_score(per, pbr, roe)
    if macd_1d in _NO_DATA and rsi_1d in _NO_DATA and fund == 0:
        return rules.NO_DATA
    tech = ruleset.macd_score(macd_1d) + ruleset.rsi_score(rsi_1d)
    # '강력' 등급에는 기술 점수의 같은 방향 확증을 요구한다 — 재무 점수 최대치(±3)가 장기
    # 임계값(3)과 같아서, 예전에는 기술 신호가 없거나 계산 불가여도 PER/PBR/ROE 만으로
    # 강력매수/강력매도가 나왔다. 입력 절반이 결측인 상태의 최고 확신 판정을 막는다.
    confirm = tech if ruleset.long_strong_requires_tech_confirm else None
    return ruleset.level5(tech + fund, ruleset.long_strong, confirm=confirm)


def short_term_score(macd_60m, rsi_60m, *,
                     ruleset: rules.RuleSet = rules.BASELINE) -> int | None:
    """단기(60분봉) 스코어 합. 임계값은 ruleset.short_strong (short_term_view 와 동일 기준)."""
    if macd_60m in _NO_DATA and rsi_60m in _NO_DATA:
        return None
    return ruleset.macd_score(macd_60m) + ruleset.rsi_score(rsi_60m)


def long_term_score(macd_1d, rsi_1d, per, pbr, roe, *,
                    ruleset: rules.RuleSet = rules.BASELINE) -> int | None:
    """장기(일봉+재무) 스코어 합. 임계값은 ruleset.long_strong (long_term_view 와 동일 기준)."""
    fund = ruleset.fundamental_score(per, pbr, roe)
    if macd_1d in _NO_DATA and rsi_1d in _NO_DATA and fund == 0:
        return None
    tech = ruleset.macd_score(macd_1d) + ruleset.rsi_score(rsi_1d)
    return tech + fund


# ────────────────────────────────────────────
# 기여요인 분해 — 화면이 점수를 재계산하지 않도록 백엔드가 만들어 보낸다.
#
# 예전에는 web/src/utils/factorScoring.ts 가 점수표·임계값·설명문을 TS 로 복제해 스스로
# 계산했고(주석에 "백엔드와 불일치할 수 있으므로 화면은 프론트 합계를 우선"이라고 명시),
# 그래서 화면 숫자와 실제 판정 근거가 갈라질 수 있었다. 이제 여기가 유일한 계산 지점이다.
# ────────────────────────────────────────────

def _fmt(value, digits: int, suffix: str = "") -> str:
    return f"{value:.{digits}f}{suffix}" if value is not None else rules.NO_DATA


def _row(key: str, label: str, score: int) -> dict:
    return {
        "key": key,
        "label": label,
        "score": score,
        "max_abs": rules.MAX_ABS[key],
        "rule": rules.RULE_TEXT[key](score),
    }


def factor_rows(factors: dict, view: str, *,
                ruleset: rules.RuleSet = rules.BASELINE) -> list[dict]:
    """판정 기여요인 분해. view 는 "short"(60분봉 MACD·RSI) 또는 "long"(일봉+재무).

    factors 는 collector 가 만든 스냅샷 항목(macd_1d/rsi_1d/rsi_value_1d/macd_60m/... /per/pbr/roe).
    """
    if view == "short":
        macd_label = factors.get("macd_60m") or rules.NO_DATA
        rsi_label = factors.get("rsi_60m") or rules.NO_DATA
        rsi_value = factors.get("rsi_value_60m")
    else:
        macd_label = factors.get("macd_1d") or rules.NO_DATA
        rsi_label = factors.get("rsi_1d") or rules.NO_DATA
        rsi_value = factors.get("rsi_value_1d")

    rsi_suffix = f" · RSI {rsi_value:.1f}" if rsi_value is not None else ""
    rows = [
        _row("macd", f"MACD {macd_label}", ruleset.macd_score(macd_label)),
        _row("rsi", f"RSI {rsi_label}{rsi_suffix}", ruleset.rsi_score(rsi_label)),
    ]
    if view == "short":
        return rows

    per, pbr, roe = factors.get("per"), factors.get("pbr"), factors.get("roe")
    rows.extend([
        _row("per", f"PER {_fmt(per, 1, '배')}", ruleset.per_band.score(per)),
        _row("pbr", f"PBR {_fmt(pbr, 2, '배')}", ruleset.pbr_band.score(pbr)),
        _row("roe", f"ROE {_fmt(roe, 1, '%')}", ruleset.roe_band.score(roe)),
    ])
    return rows


def decision_thresholds(ruleset: rules.RuleSet = rules.BASELINE) -> dict:
    """화면이 판정 규칙을 하드코딩하지 않도록 임계값을 함께 내려준다.

    프론트는 예전에 TAB_THRESHOLD={short:2,long:3} 을 복제해 두고 "합계가 +3 이상이면 매수"
    라는 **틀린** 캡션을 렌더했다(실제 규칙은 +1 이상 매수, +3 이상 강력매수).
    """
    return {
        "weak": ruleset.weak_cutoff,
        "short_strong": ruleset.short_strong,
        "long_strong": ruleset.long_strong,
        "long_strong_requires_tech_confirm": ruleset.long_strong_requires_tech_confirm,
    }
