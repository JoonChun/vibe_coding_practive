"""KIS 분봉(FHKST03010230) 파서 + 60분봉 리샘플러.

이 경로는 KIS 자격증명 없이 개발되어 **실제 HTTP 응답으로 검증되지 않았다.** 필드명·페이징은
공식 예제 3곳 교차확인이지만, 실환경에서 조용히 틀리는 것을 막는 유일한 안전망이 이 테스트다.
그래서 응답 픽스처를 공식 COLUMN_MAPPING 필드명 그대로 만들어 파서를 고정한다.

특히 잠그는 것:
  · 분봉 종가는 stck_prpr (일봉의 stck_clpr 이 아니다 — 재사용하면 전 종목 close 가 None)
  · 진행 중인 마지막 60분 구간은 버린다 (미완성 OHLC 로 판정이 봉 중간마다 흔들리지 않게)
"""
import pandas as pd

import crawler


def _minute_row(date: str, hhmmss: str, o, h, low, c, vol) -> dict:
    """공식 chk_inquire_time_dailychartprice.py COLUMN_MAPPING 의 필드명을 그대로 사용."""
    return {
        "stck_bsop_date": date,
        "stck_cntg_hour": hhmmss,
        "stck_oprc": str(o),
        "stck_hgpr": str(h),
        "stck_lwpr": str(low),
        "stck_prpr": str(c),      # ★ 분봉 종가
        "cntg_vol": str(vol),
        "acml_tr_pbmn": "999999",
    }


# ── 파서 ──

def test_parse_uses_stck_prpr_as_close():
    """일봉의 stck_clpr 을 재사용하면 close 가 전부 None 이 된다 — 그 회귀를 막는다."""
    rows = [_minute_row("20260724", "093000", 100, 105, 99, 103, 500)]
    parsed = crawler._parse_kis_minute_rows(rows)

    assert len(parsed) == 1
    assert parsed[0]["close"] == 103.0
    assert parsed[0]["open"] == 100.0
    assert parsed[0]["high"] == 105.0
    assert parsed[0]["low"] == 99.0
    assert parsed[0]["volume"] == 500
    assert parsed[0]["date"] == "202607240930"  # 초는 버리고 분까지


def test_parse_skips_malformed_rows_without_failing_the_batch():
    rows = [
        _minute_row("20260724", "093000", 100, 105, 99, 103, 500),
        {"stck_bsop_date": "20260724"},                      # 시각 없음
        {"stck_bsop_date": "bad", "stck_cntg_hour": "093100"},  # 날짜 형식 오류
        {**_minute_row("20260724", "093200", 1, 1, 1, 1, 1), "stck_prpr": "N/A"},  # 캐스팅 실패
        _minute_row("20260724", "093300", 101, 106, 100, 104, 600),
    ]
    parsed = crawler._parse_kis_minute_rows(rows)

    assert [p["date"] for p in parsed] == ["202607240930", "202607240933"]


def test_parse_missing_volume_defaults_to_zero():
    rows = [{**_minute_row("20260724", "093000", 100, 105, 99, 103, 0), "cntg_vol": None}]
    assert crawler._parse_kis_minute_rows(rows)[0]["volume"] == 0


# ── 60분봉 리샘플 ──

def _minutes_df(specs: list[tuple[str, float, float, float, float, int]]) -> pd.DataFrame:
    return pd.DataFrame([
        {"date": d, "open": o, "high": h, "low": low, "close": c, "volume": v}
        for d, o, h, low, c, v in specs
    ])


def test_resample_aggregates_ohlcv_correctly():
    # 09:00~09:59 구간을 완전히 채운다(마지막 봉 09:59 → 구간 완료로 인정).
    specs = [(f"202607240{9}{m:02d}", 100 + m, 110 + m, 90 + m, 105 + m, 10)
             for m in range(0, 60)]
    out = crawler.resample_minutes_to_60m(_minutes_df(specs))

    assert out is not None and len(out) == 1
    row = out.iloc[0]
    assert row["open"] == 100          # first
    assert row["high"] == 110 + 59     # max
    assert row["low"] == 90            # min
    assert row["close"] == 105 + 59    # last
    assert row["volume"] == 600        # sum
    assert row["date"] == "202607240900"


def test_resample_drops_incomplete_trailing_bar():
    """진행 중인 마지막 구간은 버린다 — 미완성 봉이 지표에 들어가면 판정이 흔들린다."""
    # 09:00~09:59 완주 + 10:00~10:04 만 있는 미완성 구간
    specs = [(f"202607240{9}{m:02d}", 100, 110, 90, 105, 10) for m in range(0, 60)]
    specs += [(f"2026072410{m:02d}", 200, 210, 190, 205, 10) for m in range(0, 5)]

    out = crawler.resample_minutes_to_60m(_minutes_df(specs))

    assert out is not None and len(out) == 1
    assert out.iloc[0]["date"] == "202607240900"  # 10시 봉은 제외됨


def test_resample_keeps_complete_trailing_bar():
    specs = [(f"202607240{9}{m:02d}", 100, 110, 90, 105, 10) for m in range(0, 60)]
    specs += [(f"2026072410{m:02d}", 200, 210, 190, 205, 10) for m in range(0, 60)]

    out = crawler.resample_minutes_to_60m(_minutes_df(specs))

    assert out is not None and len(out) == 2
    assert list(out["date"]) == ["202607240900", "202607241000"]


def test_resample_returns_tz_aware_index_matching_yf_contract():
    """collector._df_to_candle_items_minute 가 인덱스의 .timestamp() 를 쓰므로 tz 가 필요하다."""
    specs = [(f"202607240{9}{m:02d}", 100, 110, 90, 105, 10) for m in range(0, 60)]
    out = crawler.resample_minutes_to_60m(_minutes_df(specs))

    assert out.index.tz is not None
    assert str(out.index.tz) == "Asia/Seoul"
    # yfinance 경로와 동일한 컬럼 계약
    assert list(out.columns) == ["date", "open", "high", "low", "close", "volume"]


def test_resample_handles_empty_and_bad_input():
    assert crawler.resample_minutes_to_60m(None) is None
    assert crawler.resample_minutes_to_60m(pd.DataFrame()) is None
    assert crawler.resample_minutes_to_60m(pd.DataFrame({"close": [1]})) is None
    # 날짜가 전부 파싱 불가
    bad = pd.DataFrame({
        "date": ["not-a-date"], "open": [1.0], "high": [1.0],
        "low": [1.0], "close": [1.0], "volume": [1],
    })
    assert crawler.resample_minutes_to_60m(bad) is None


def test_resample_single_incomplete_bar_returns_none():
    """구간이 하나뿐이고 그게 미완성이면 쓸 수 있는 봉이 없다."""
    specs = [(f"2026072409{m:02d}", 100, 110, 90, 105, 10) for m in range(0, 3)]
    assert crawler.resample_minutes_to_60m(_minutes_df(specs)) is None


# ── 일자별 페이징 ──

def test_one_day_fetch_pages_backwards_and_dedupes(monkeypatch):
    """응답의 최소 체결시각을 다음 호출 기준시각으로 재투입하고, 경계 중복은 제거한다."""
    calls = []

    class _Resp:
        def __init__(self, rows):
            self._rows = rows

        def raise_for_status(self):
            pass

        def json(self):
            return {"rt_cd": "0", "output2": self._rows}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(params["FID_INPUT_HOUR_1"])
        cursor = params["FID_INPUT_HOUR_1"]
        if cursor == "153000":
            # 120건 꽉 채운 페이지(11:00~12:59) → 다음 페이지 요청 유발
            rows = [_minute_row("20260724", f"{11 + m // 60:02d}{m % 60:02d}00", 1, 1, 1, 1, 1)
                    for m in range(120)]
            return _Resp(rows)
        # 두 번째 페이지: 경계 봉(1100) 중복 포함 + 개장 시각 도달
        return _Resp([
            _minute_row("20260724", "110000", 1, 1, 1, 1, 1),
            _minute_row("20260724", "090000", 2, 2, 2, 2, 2),
        ])

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    monkeypatch.setattr(crawler.kis_auth, "kis_throttle", lambda: None)

    rows = crawler._fetch_kis_minute_one_day("005930", "tok", "20260724")

    assert calls == ["153000", "110000"]              # 최소 시각을 커서로 재투입
    dates = [r["date"] for r in rows]
    assert len(dates) == len(set(dates)), "페이지 경계 봉이 중복됐다"
    assert dates == sorted(dates), "오름차순 정렬이 아니다"
    assert "202607240900" in dates
    # 내부 필드는 반환에서 제거
    assert all("_time" not in r for r in rows)


def test_one_day_fetch_survives_http_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("timeout")

    monkeypatch.setattr(crawler.requests, "get", boom)
    monkeypatch.setattr(crawler.kis_auth, "kis_throttle", lambda: None)

    assert crawler._fetch_kis_minute_one_day("005930", "tok", "20260724") == []


def test_minute_fetch_skips_non_trading_days(monkeypatch):
    """휴장일에 헛 왕복하지 않는다 — 호출량이 이미 큰 경로라 낭비를 막아야 한다."""
    asked = []

    def fake_day(code, token, date_str):
        asked.append(date_str)
        return [_minute_row("x", "090000", 1, 1, 1, 1, 1)] and [
            {"date": f"{date_str}0900", "open": 1.0, "high": 1.0,
             "low": 1.0, "close": 1.0, "volume": 1}
        ]

    monkeypatch.setattr(crawler, "_fetch_kis_minute_one_day", fake_day)

    df = crawler.fetch_kis_minute_ohlcv("005930", "tok", 3)

    assert df is not None and len(asked) == 3
    import market_calendar
    for date_str in asked:
        d = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        assert market_calendar.is_trading_day(d), f"{date_str} 는 휴장일인데 조회했다"


def test_minute_fetch_returns_none_when_nothing_collected(monkeypatch):
    monkeypatch.setattr(crawler, "_fetch_kis_minute_one_day", lambda c, t, d: [])
    assert crawler.fetch_kis_minute_ohlcv("005930", "tok", 3) is None
