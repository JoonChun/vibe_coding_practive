"""판정 백테스트 — "이 앱 판정대로 샀으면?"

앱의 기계적 판정 로직(indicators)을 과거 각 시점의 일봉에 재적용해:
  · 매수 판정의 적중률(N일 뒤 상승 비율)·평균 선행수익률
  · 판정을 따라 매수/현금 전환했을 때의 가상 누적수익률 vs 단순 보유(buy&hold)
를 산출한다.

초기 버전은 재무 지표의 과거값이 없으므로 **기술적 판정(일봉 MACD+RSI)만** 사용한다
(long_term_view 에 재무 None 전달 → 기술 점수만). 과거 성과는 미래를 보장하지 않으며
수수료·슬리피지 미반영이다.

순수 계산부(run_signal_backtest)는 외부 의존 없이 df만 받으므로 단위테스트가 쉽다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from config import TIMEZONE

_BUY_VIEWS = {"매수", "강력매수"}
_SELL_VIEWS = {"매도", "강력매도"}

# MACD(MACD_SLOW=26 + MACD_SIGNAL=9)에 필요한 최소 봉 수 — 이보다 앞선 구간은 판정 불가.
# indicators._MIN_BARS_MACD 와 동일 값을 상수로 둔다(import 시점에 ta 의존 회피 → 테스트 용이).
_MIN_BARS = 35
# O(n²) 재계산 비용을 제한하기 위해 최근 N봉으로 캡.
_MAX_BARS = 400


def _daily_view(sub: pd.DataFrame) -> str:
    """일봉 슬라이스의 기술적 장기 판정(재무 제외). '데이터부족'/5단계 중 하나."""
    import indicators  # 지연 import — 모듈 로드 시 ta 의존을 강제하지 않음

    macd = indicators.macd_cross_signal(sub)
    rsi = indicators.rsi_zone_signal(sub)
    return indicators.long_term_view(macd, rsi, None, None, None)


def _epoch_to_date(t) -> str | None:
    try:
        return datetime.fromtimestamp(int(t), ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def run_signal_backtest(df: pd.DataFrame, horizon: int = 20) -> dict:
    """df: 오름차순 일봉('close' 필수, 't' 있으면 날짜 표기). 순수 계산."""
    if df is None or "close" not in df.columns:
        raise ValueError("close 컬럼이 필요합니다.")
    if len(df) > _MAX_BARS:
        df = df.iloc[-_MAX_BARS:].reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    closes = [float(c) for c in df["close"].tolist()]
    n = len(closes)
    has_t = "t" in df.columns

    buy_fwd: list[float] = []
    sell_fwd: list[float] = []

    # ── 선행수익률 적중률 (t 시점 판정 → t+horizon 수익률) ──
    last_eval = n - horizon  # exclusive
    evaluated = 0
    for t in range(_MIN_BARS - 1, last_eval):
        entry = closes[t]
        if entry <= 0:
            continue
        view = _daily_view(df.iloc[: t + 1])
        if view == "데이터부족":
            continue
        fwd = (closes[t + horizon] - entry) / entry * 100
        if view in _BUY_VIEWS:
            buy_fwd.append(fwd)
        elif view in _SELL_VIEWS:
            sell_fwd.append(fwd)
        evaluated += 1

    def _side(fwds: list[float], win) -> dict:
        if not fwds:
            return {"signals": 0, "hit_rate": None, "avg_forward_pct": None}
        hits = sum(1 for f in fwds if win(f))
        return {
            "signals": len(fwds),
            "hit_rate": round(hits / len(fwds) * 100, 1),
            "avg_forward_pct": round(sum(fwds) / len(fwds), 2),
        }

    # ── "판정 따라가기" 가상 누적수익률 vs 단순 보유 ──
    # 매수 판정이면 다음날 롱, 아니면 현금(수익 0). 매일 재판정.
    start = _MIN_BARS - 1
    equity = 1.0
    position = 0
    curve: list[dict] = []
    for t in range(start, n):
        if t > start and position == 1:
            r = closes[t] / closes[t - 1] - 1
            equity *= 1 + r
        view = _daily_view(df.iloc[: t + 1])
        position = 1 if view in _BUY_VIEWS else 0
        bh = closes[t] / closes[start] - 1
        curve.append({
            "t": int(df.iloc[t]["t"]) if has_t else t,
            "strategy": round((equity - 1) * 100, 2),
            "buyhold": round(bh * 100, 2),
        })

    strategy_return = round((equity - 1) * 100, 2)
    buy_hold_return = round((closes[-1] / closes[start] - 1) * 100, 2) if closes[start] > 0 else 0.0

    # 곡선 다운샘플(최대 ~80점)
    if len(curve) > 80:
        step = len(curve) // 80 + 1
        curve = curve[::step] + [curve[-1]]

    start_date = _epoch_to_date(df.iloc[start]["t"]) if has_t else None
    end_date = _epoch_to_date(df.iloc[-1]["t"]) if has_t else None

    return {
        "horizon_days": horizon,
        "evaluated_days": evaluated,
        "start_date": start_date,
        "end_date": end_date,
        "buy": _side(buy_fwd, lambda f: f > 0),
        "sell": _side(sell_fwd, lambda f: f < 0),
        "strategy_return_pct": strategy_return,
        "buy_hold_return_pct": buy_hold_return,
        "curve": curve,
    }


class InsufficientHistoryError(Exception):
    """백테스트에 필요한 일봉 이력이 부족한 경우."""


def _load_daily(code: str) -> pd.DataFrame | None:
    """일봉 이력 로드 — 저장소(collector 누적) 우선, 부족하면 yfinance 3년 폴백."""
    import db

    stored = db.get_candles_store(code, "1d", 800)
    if stored and len(stored) >= _MIN_BARS + 25:
        return pd.DataFrame(stored)

    try:
        import crawler

        df = crawler.fetch_yf_ohlcv(code, interval="1d", period="3y")
        if df is not None and not df.empty and "close" in df.columns:
            return df
    except Exception as e:
        print(f"[backtest] yfinance 폴백 실패 ({code}): {e}")

    return pd.DataFrame(stored) if stored else None


def signal_backtest(code: str, horizon: int = 20) -> dict:
    import db

    normalized = db.normalize_code(code)
    df = _load_daily(normalized)
    if df is None or "close" not in df.columns or len(df) < _MIN_BARS + horizon:
        raise InsufficientHistoryError(
            "백테스트에 필요한 일봉 이력이 부족합니다. 관심종목으로 등록되면 "
            "매 수집 사이클마다 이력이 축적됩니다."
        )
    result = run_signal_backtest(df, horizon)
    result["code"] = normalized
    return result
