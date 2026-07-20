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
import pandas as pd

from .timeseries import downsample, epoch_to_date

_BUY_VIEWS = {"매수", "강력매수"}
_SELL_VIEWS = {"매도", "강력매도"}

# MACD(MACD_SLOW=26 + MACD_SIGNAL=9)에 필요한 최소 봉 수 — 이보다 앞선 구간은 판정 불가.
# indicators._MIN_BARS_MACD 와 동일 값을 상수로 둔다(import 시점에 ta 의존 회피 → 테스트 용이).
_MIN_BARS = 35
# O(n²) 재계산 비용을 제한하기 위해 최근 N봉으로 캡.
_MAX_BARS = 400


def _build_view_at(df: pd.DataFrame):
    """MACD/RSI 를 전체 시계열에 대해 1회만 계산하고, 인덱스 i(=[:i+1] 슬라이스 끝)의
    기술적 장기 판정을 O(1) 로 돌려주는 함수를 만든다.

    MACD(EMA)·RSI(Wilder)는 인과적(recursive)이라 index i 의 값은 prefix[:i+1] 로
    계산한 값과 동일하다 → 매 시점 슬라이스 재계산(O(n²)) 대신 1회 계산으로 대체.
    라벨 문자열은 indicators.macd_cross_signal/rsi_zone_signal 과 동일 규칙을 따른다.
    """
    import ta.momentum
    import ta.trend

    import indicators
    from config import (
        MACD_FAST, MACD_SIGNAL, MACD_SLOW,
        RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_PERIOD,
    )

    close = df["close"].astype(float)
    macd_obj = ta.trend.MACD(
        close=close, window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL
    )
    macd_line = macd_obj.macd().tolist()
    signal_line = macd_obj.macd_signal().tolist()
    rsi = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi().tolist()

    def _nan(v) -> bool:
        return v is None or v != v  # NaN != NaN

    def _macd_label(i: int) -> str:
        if i < 1:
            return "데이터부족"
        pm, cm, ps, cs = macd_line[i - 1], macd_line[i], signal_line[i - 1], signal_line[i]
        if any(_nan(v) for v in (pm, cm, ps, cs)):
            return "데이터부족"
        if pm <= ps and cm > cs:
            return "골든크로스(진입)"
        if pm >= ps and cm < cs:
            return "데드크로스(매도)"
        return "진입구간" if cm > cs else "매도구간"

    def _rsi_label(i: int) -> str:
        v = rsi[i]
        if _nan(v):
            return "데이터부족"
        if v <= RSI_OVERSOLD:
            return "과매도(진입)"
        if v >= RSI_OVERBOUGHT:
            return "과매수(매도)"
        return "중립"

    def view_at(i: int) -> str:
        return indicators.long_term_view(_macd_label(i), _rsi_label(i), None, None, None)

    return view_at


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

    # 지표 1회 계산 → 인덱스별 판정 O(1) (기존 슬라이스 재계산 O(n²) 대체)
    view_at = _build_view_at(df)

    buy_fwd: list[float] = []
    sell_fwd: list[float] = []

    # ── 선행수익률 적중률 (t 시점 판정 → t+horizon 수익률) ──
    last_eval = n - horizon  # exclusive
    evaluated = 0
    for t in range(_MIN_BARS - 1, last_eval):
        entry = closes[t]
        if entry <= 0:
            continue
        view = view_at(t)
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
        view = view_at(t)
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
    curve = downsample(curve)

    start_date = epoch_to_date(df.iloc[start]["t"]) if has_t else None
    end_date = epoch_to_date(df.iloc[-1]["t"]) if has_t else None

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
