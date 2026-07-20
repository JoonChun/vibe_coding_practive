"""적립식 백테스트 (DCA) — "매달 N주(또는 N원어치)씩 샀다면 지금 얼마?"

판정 로직 없이 정기(월별) 매수만 시뮬레이션한다. 월봉은 기존 candles 서비스
(KIS 월봉 / yfinance 폴백)를 재사용한다.

한계: 수수료·세금·슬리피지 미반영, 수정주가 기준(candles 소스에 따름), 배당 미반영,
해외/원화 환율 미반영. 과거 성과는 미래를 보장하지 않는다.

순수 계산부(run_dca_backtest)는 items 리스트만 받아 단위테스트가 쉽다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE


class InsufficientHistoryError(Exception):
    """DCA 에 필요한 월봉 이력이 부족한 경우."""


def _epoch_to_date(t) -> str | None:
    try:
        return datetime.fromtimestamp(int(t), ZoneInfo(TIMEZONE)).strftime("%Y-%m")
    except (TypeError, ValueError, OSError):
        return None


def run_dca_backtest(items: list[dict], mode: str = "qty", per: float = 1) -> dict:
    """items: [{t, close, ...}] (정렬 무관). mode 'qty'=매월 per주, 'amount'=매월 per원어치."""
    if mode not in ("qty", "amount"):
        raise ValueError(f"잘못된 mode: {mode}")
    if per <= 0:
        raise ValueError("per 는 0보다 커야 합니다.")

    rows = []
    for it in items:
        c = it.get("close")
        try:
            c = float(c)
        except (TypeError, ValueError):
            continue
        if c > 0 and it.get("t") is not None:
            rows.append((int(it["t"]), c))
    if len(rows) < 2:
        raise InsufficientHistoryError("적립식 백테스트에 필요한 월봉 이력이 부족합니다.")
    rows.sort(key=lambda x: x[0])

    shares = 0.0
    cost = 0.0
    curve: list[dict] = []
    for t, price in rows:
        if mode == "qty":
            shares += per
            cost += price * per
        else:  # amount — 소수점 체결 허용(시뮬레이션)
            shares += per / price
            cost += per
        value = shares * price
        curve.append({
            "t": t,
            "principal": round(cost),
            "value": round(value),
        })

    last_price = rows[-1][1]
    eval_value = shares * last_price
    profit = eval_value - cost
    return_pct = (profit / cost * 100) if cost > 0 else 0.0

    if len(curve) > 80:
        step = len(curve) // 80 + 1
        curve = curve[::step] + [curve[-1]]

    return {
        "mode": mode,
        "per": per,
        "buys": len(rows),
        "total_shares": round(shares, 4),
        "avg_price": round(cost / shares, 2) if shares > 0 else None,
        "current_price": round(last_price, 2),
        "principal": round(cost),
        "eval_value": round(eval_value),
        "profit": round(profit),
        "return_pct": round(return_pct, 2),
        "start_date": _epoch_to_date(rows[0][0]),
        "end_date": _epoch_to_date(rows[-1][0]),
        "curve": curve,
    }


def dca_backtest(code: str, mode: str = "qty", per: float = 1, months: int = 120) -> dict:
    import db

    from . import candles as candles_service

    normalized = db.normalize_code(code)
    # 월봉 재사용(KIS 월봉/ yfinance 폴백). 최대 130개월 조회 후 최근 months 개월로 트림.
    res = candles_service.get_candles(normalized, "1M", 130)
    items = res.get("items", []) if res else []
    if months and len(items) > months:
        items = items[-months:]
    if len(items) < 2:
        raise InsufficientHistoryError(
            "적립식 백테스트에 필요한 월봉 이력이 부족합니다."
        )
    result = run_dca_backtest(items, mode, per)
    result["code"] = normalized
    result["source"] = res.get("source")
    return result
