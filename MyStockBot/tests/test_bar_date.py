"""크론 수집 결과의 '기준 거래일'(bar_date) 파싱 — 휴장일 중복 기록 방지의 핵심.

시트 '날짜' 컬럼에 실행일이 아니라 이 값을 쓰기 때문에, 휴장일에 크론이 돌아 직전
거래일 종가를 받아도 그 종가의 원래 날짜로 기록된다(→ (날짜,종목코드) 중복 스킵이 걸림).
"""
import pandas as pd

import crawler


def test_bar_date_from_kis_style_date_column():
    df = pd.DataFrame({"date": ["20260813", "20260814"], "close": [100, 110]})
    assert crawler._bar_date(df) == "2026-08-14"


def test_bar_date_ignores_minute_suffix():
    # 분봉 포맷(YYYYMMDDHHMM)이 들어와도 앞 8자리(거래일)만 취한다.
    df = pd.DataFrame({"date": ["202608141530"], "close": [110]})
    assert crawler._bar_date(df) == "2026-08-14"


def test_bar_date_returns_none_on_bad_input():
    assert crawler._bar_date(None) is None
    assert crawler._bar_date(pd.DataFrame({"date": [], "close": []})) is None
    assert crawler._bar_date(pd.DataFrame({"date": ["not-a-date"], "close": [1]})) is None
    # date 컬럼 자체가 없어도 예외 없이 None.
    assert crawler._bar_date(pd.DataFrame({"close": [1]})) is None


def test_empty_result_carries_bar_date_key():
    # 실패 종목도 동일 스키마여야 호출부가 .get("bar_date") 로 균일하게 다룰 수 있다.
    assert "bar_date" in crawler._EMPTY_RESULT
    assert crawler._EMPTY_RESULT["bar_date"] is None
