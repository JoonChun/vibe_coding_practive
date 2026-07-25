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
import logging
import math

import pandas as pd

from .timeseries import downsample, epoch_to_date

logger = logging.getLogger(__name__)

_BUY_VIEWS = {"매수", "강력매수"}
_SELL_VIEWS = {"매도", "강력매도"}

# 적중률 신뢰구간 z값(95%).
_Z_95 = 1.96

# MACD(MACD_SLOW=26 + MACD_SIGNAL=9)에 필요한 최소 봉 수 — 이보다 앞선 구간은 판정 불가.
# indicators._MIN_BARS_MACD 와 동일 값을 상수로 둔다(import 시점에 ta 의존 회피 → 테스트 용이).
_MIN_BARS = 35
# O(n²) 재계산 비용을 제한하기 위해 최근 N봉으로 캡.
# 이 캡이 걸리면(=이력이 더 길면) 응답의 truncated/notes 로 반드시 알린다 — 조용히
# 1.6년치만 계산해 놓고 "과거 성과"라고 보여주면 사용자가 기간을 오해한다.
_MAX_BARS = 400

# 겹침 보정 표본이 이보다 적으면 적중률을 신뢰할 수 없다고 표시한다(≈독립 관측 10건).
_MIN_EFFECTIVE_SAMPLE = 10


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


def _sanitize_closes(raw: list) -> list[float]:
    """0·음수·NaN·None 종가를 직전 유효값으로 forward-fill(선행 결측은 back-fill).

    거래정지 봉(KIS stck_clpr="0")·결측이 섞이면 뒤 계산의 ZeroDivision/NaN 오염을
    유발하므로, 계산 전에 항상 양(+)의 연속 시계열로 정제한다. 유효값이 하나도 없으면
    ValueError.
    """
    def _valid(c):
        try:
            f = float(c)
        except (TypeError, ValueError):
            return None
        return f if (f == f and f > 0) else None  # NaN != NaN

    filled: list[float | None] = []
    last: float | None = None
    for c in raw:
        v = _valid(c)
        if v is not None:
            last = v
        filled.append(last)
    first_valid = next((c for c in filled if c is not None), None)
    if first_valid is None:
        raise ValueError("유효한 종가가 없습니다(전부 0/결측).")
    return [c if c is not None else first_valid for c in filled]


def _wilson_interval(hits: int, n: int) -> list[float] | None:
    """이항 비율의 Wilson score 95% 신뢰구간을 [하한%, 상한%] 로 반환. n<=0 이면 None.

    표본이 적을 때 정규근사(Wald)는 구간이 [0,1] 밖으로 나가거나 지나치게 좁아지므로
    Wilson 을 쓴다 — "적중률 70%"가 표본 10건이면 사실상 아무 말도 아니라는 점을
    숫자로 드러내는 것이 목적이다.
    """
    if n <= 0:
        return None
    p = hits / n
    denom = 1 + _Z_95**2 / n
    center = (p + _Z_95**2 / (2 * n)) / denom
    margin = _Z_95 * math.sqrt(p * (1 - p) / n + _Z_95**2 / (4 * n * n)) / denom
    return [
        round(max(0.0, center - margin) * 100, 1),
        round(min(1.0, center + margin) * 100, 1),
    ]


def _effective_sample(indices: list[int], horizon: int) -> int:
    """겹치는 선행구간을 보정한 '독립 표본 수'.

    t 시점 판정의 성과를 t+horizon 으로 재기 때문에, horizon 안에 몰려 있는 판정들은
    거의 같은 가격 움직임을 본다(예: horizon=20 이면 연속 20일치 매수 신호가 사실상
    관측 1건). 신호 인덱스를 훑어 서로 horizon 이상 떨어진 것만 그리디로 세어, 실제
    시간적 분포를 반영한 독립 관측 수를 구한다 — 신호가 흩어져 있으면 표본이 그만큼
    많이 인정되고, 한 구간에 뭉쳐 있으면 1건으로 깎인다.
    """
    if not indices:
        return 0
    step = max(1, horizon)
    count = 0
    last_taken = None
    for i in sorted(indices):
        if last_taken is None or i - last_taken >= step:
            count += 1
            last_taken = i
    return count


def run_signal_backtest(df: pd.DataFrame, horizon: int = 20) -> dict:
    """df: 오름차순 일봉('close' 필수, 't' 있으면 날짜 표기). 순수 계산."""
    if df is None or "close" not in df.columns:
        raise ValueError("close 컬럼이 필요합니다.")
    bars_available = len(df)
    truncated = bars_available > _MAX_BARS
    if truncated:
        df = df.iloc[-_MAX_BARS:].reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    # 0/NaN 종가로 인한 ZeroDivision·NaN 오염 방지(계약을 순수함수에서도 자체 방어)
    closes = _sanitize_closes(df["close"].tolist())
    n = len(closes)
    if n < _MIN_BARS + horizon:
        raise ValueError(
            f"백테스트에 최소 {_MIN_BARS + horizon}봉이 필요합니다(현재 {n}봉)."
        )
    df = df.copy()
    df["close"] = closes  # 정제된 종가로 지표도 계산되도록 동기화
    has_t = "t" in df.columns

    # 지표 1회 계산 → 인덱스별 판정 O(1) (기존 슬라이스 재계산 O(n²) 대체)
    view_at = _build_view_at(df)

    # (봉 인덱스, 선행수익률) — 인덱스는 겹침 보정 표본 계산에 쓴다.
    buy_fwd: list[tuple[int, float]] = []
    sell_fwd: list[tuple[int, float]] = []

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
            buy_fwd.append((t, fwd))
        elif view in _SELL_VIEWS:
            sell_fwd.append((t, fwd))
        evaluated += 1

    def _side(samples: list[tuple[int, float]], win) -> dict:
        if not samples:
            return {
                "signals": 0,
                "effective_signals": 0,
                "hit_rate": None,
                "hit_rate_ci": None,
                "avg_forward_pct": None,
                "low_confidence": True,
            }
        fwds = [f for _, f in samples]
        hits = sum(1 for f in fwds if win(f))
        total = len(fwds)
        n_eff = _effective_sample([i for i, _ in samples], horizon)
        # 신뢰구간은 원 표본이 아니라 겹침 보정 표본으로 계산한다(과신 방지).
        hits_eff = round(hits / total * n_eff)
        return {
            "signals": total,
            "effective_signals": n_eff,
            "hit_rate": round(hits / total * 100, 1),
            "hit_rate_ci": _wilson_interval(hits_eff, n_eff),
            "avg_forward_pct": round(sum(fwds) / total, 2),
            "low_confidence": n_eff < _MIN_EFFECTIVE_SAMPLE,
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

    buy = _side(buy_fwd, lambda f: f > 0)
    sell = _side(sell_fwd, lambda f: f < 0)

    # 가정·한계를 응답에 함께 실어 화면이 반드시 노출하게 한다(DCA notes 와 동일 관례).
    notes = [
        "수수료·세금·슬리피지 미반영",
        "재무지표(PER/PBR/ROE) 미반영 — 기술적 판정(MACD+RSI)만 재적용",
    ]
    if truncated:
        notes.append(
            f"계산 비용 제한으로 최근 {_MAX_BARS}봉만 사용(보유 이력 {bars_available}봉)"
        )
    if buy["low_confidence"] or sell["low_confidence"]:
        notes.append(
            f"겹침 보정 표본이 {_MIN_EFFECTIVE_SAMPLE}건 미만 — 적중률은 참고치로만 보세요"
        )

    return {
        "horizon_days": horizon,
        "evaluated_days": evaluated,
        "start_date": start_date,
        "end_date": end_date,
        "bars_used": n,
        "bars_available": bars_available,
        "max_bars": _MAX_BARS,
        "truncated": truncated,
        "fundamentals_included": False,
        "buy": buy,
        "sell": sell,
        "strategy_return_pct": strategy_return,
        "buy_hold_return_pct": buy_hold_return,
        "notes": notes,
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
        logger.warning(f"[backtest] yfinance 폴백 실패 ({code}): {e}")

    return pd.DataFrame(stored) if stored else None


def signal_backtest(code: str, horizon: int = 20) -> dict:
    import db

    from .timeseries import PriceDataError, detect_split_anomaly

    normalized = db.normalize_code(code)
    df = _load_daily(normalized)
    if df is None or "close" not in df.columns or len(df) < _MIN_BARS + horizon:
        raise InsufficientHistoryError(
            "백테스트에 필요한 일봉 이력이 부족합니다. 관심종목으로 등록되면 "
            "매 수집 사이클마다 이력이 축적됩니다. (데이터 소스 일시 오류일 수도 있으니 "
            "잠시 후 다시 시도해 주세요.)"
        )
    # 수정주가 미조정/소스 혼용으로 인접 봉이 비정상 점프하면 수익률이 폭발한다 →
    # 잘못된 숫자를 보여주느니 계산을 중단하고 재수집을 유도.
    if detect_split_anomaly(df["close"].tolist()) is not None:
        raise PriceDataError(
            "가격 데이터에 이상(액면분할 미조정 추정)이 감지되어 백테스트를 중단했습니다. "
            "잠시 후 다시 시도하면 재수집된 데이터로 계산됩니다."
        )
    result = run_signal_backtest(df, horizon)
    result["code"] = normalized
    return result
