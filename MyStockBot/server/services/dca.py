"""적립식 백테스트 (DCA) — "그때부터 매주/매월/매분기 사왔다면 지금 얼마?"

판정 로직 없이 정기 매수만 시뮬레이션한다. 주기(freq)에 따라 주봉(1w)/월봉(1M)을
candles 서비스로 조회하고, KIS 100건 상한으로 장기 요청이 잘리면 yfinance 장기(max)
시계열로 보강한다.

한계: 수수료·세금·슬리피지 미반영, 수정주가 기준(소스에 따름), **배당 재투자 미지원
(배당 데이터 미연동)**, 해외/원화 환율 미반영. 과거 성과는 미래를 보장하지 않는다.
(응답 notes 에 이 가정들을 함께 실어 화면에서 오해하지 않도록 한다.)

순수 계산부(run_dca_backtest)는 items 리스트만 받아 단위테스트가 쉽다.
"""
from .timeseries import downsample, epoch_to_date

# 주기 → 연간 매수 횟수
_PERIODS_PER_YEAR = {"weekly": 52, "monthly": 12, "quarterly": 4}


class InsufficientHistoryError(Exception):
    """DCA 에 필요한 이력이 부족한 경우(진짜 데이터 없음)."""


class DataSourceError(Exception):
    """시세 데이터 소스(KIS/yfinance) 일시 오류로 조회 자체가 실패한 경우."""


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

    curve = downsample(curve)

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
        "start_date": epoch_to_date(rows[0][0], "%Y-%m"),
        "end_date": epoch_to_date(rows[-1][0], "%Y-%m"),
        "curve": curve,
    }


def _chunk_last(items: list[dict], size: int) -> list[dict]:
    """오름차순 items 를 size개씩 묶어 각 그룹의 마지막(최신) 봉만 남긴다(분기 캐던스 근사)."""
    return [items[i:i + size][-1] for i in range(0, len(items), size)]


def _long_series(code: str, tf: str, want: int) -> tuple[list[dict], str | None, bool]:
    """candles 서비스로 조회하되, KIS 100건 상한 등으로 want 에 못 미치면
    yfinance 장기(period='max')로 보강. (items, source, fetch_error) 반환."""
    import crawler

    from . import candles as candles_service

    res = candles_service.get_candles(code, tf, min(max(want + 2, 130), 300))
    items = res.get("items", []) or []
    source = res.get("source")
    fetch_error = bool(res.get("fetch_error"))
    if len(items) < want:  # KIS 월/주봉은 ~100건 상한 → 장기 요청은 조용히 잘린다
        yf_int = {"1M": "1mo", "1w": "1wk"}.get(tf)
        if yf_int:
            try:
                df = crawler.fetch_yf_ohlcv(code, interval=yf_int, period="max")
                if df is not None and not df.empty:
                    y = candles_service._df_to_items_daily(df)
                    if len(y) > len(items):
                        items, source, fetch_error = y, "yfinance", False
            except Exception as e:
                print(f"[dca] yfinance 장기 보강 실패({code},{tf}): {e}")
    return items, source, fetch_error


def dca_backtest(
    code: str,
    mode: str = "qty",
    per: float = 1,
    months: int = 120,
    freq: str = "monthly",
    reinvest: bool = False,
) -> dict:
    import db

    if freq not in _PERIODS_PER_YEAR:
        raise ValueError(f"잘못된 freq: {freq}")

    normalized = db.normalize_code(code)
    ppy = _PERIODS_PER_YEAR[freq]
    want = max(2, round(months / 12 * ppy))
    tf = "1w" if freq == "weekly" else "1M"

    items, source, fetch_error = _long_series(normalized, tf, want)

    if freq == "quarterly":
        items = _chunk_last(items, 3)  # 월봉 → 3개월 묶어 분기 캐던스로 근사

    trim = -(-months // 3) if freq == "quarterly" else want  # ceil(months/3) for 분기
    trim = max(2, trim)
    if len(items) > trim:
        items = items[-trim:]

    if len(items) < 2:
        if fetch_error:
            raise DataSourceError(
                "시세 데이터 소스(KIS/yfinance) 일시 오류로 조회에 실패했습니다. "
                "잠시 후 다시 시도해 주세요."
            )
        raise InsufficientHistoryError(
            "적립식 백테스트에 필요한 이력이 부족합니다. (관심종목으로 등록하면 이력이 축적됩니다.)"
        )

    result = run_dca_backtest(items, mode, per)
    result["code"] = normalized
    result["source"] = source
    result["freq"] = freq
    result["reinvest"] = False  # 배당 데이터 미연동 — 실제 반영되지 않음(notes 참조)

    notes = ["수수료·세금·슬리피지 미반영", "수정주가 기준(소스에 따름)"]
    if freq == "quarterly":
        notes.append("분기 매수는 월봉을 3개월 단위로 축약해 근사")
    if reinvest:
        notes.append("배당 재투자는 아직 미지원(배당 데이터 미연동)이라 반영되지 않았습니다")
    got_months = round(len(items) / ppy * 12)
    if got_months < months - 1:  # 요청보다 실제 확보 기간이 짧으면 명시(조용한 잘림 방지)
        notes.append(f"데이터 한계로 요청 {months}개월 중 약 {got_months}개월만 반영")
    result["notes"] = notes
    return result
