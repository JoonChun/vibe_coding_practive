from datetime import date, timedelta

import market_calendar as mc


def test_weekend_not_trading():
    d = date(2026, 6, 1)
    while d.weekday() != 5:  # 토요일까지 전진
        d += timedelta(days=1)
    assert mc.is_trading_day(d) is False


def test_plain_weekday_is_trading():
    d = date(2026, 7, 20)
    while d.weekday() >= 5 or mc.is_holiday(d):  # 휴장 아닌 평일까지 전진
        d += timedelta(days=1)
    assert mc.is_trading_day(d) is True


def test_fixed_holidays():
    assert mc.is_holiday(date(2026, 1, 1)) is True       # 신정
    assert mc.is_holiday("2026-05-05") is True           # 어린이날
    assert mc.is_trading_day(date(2026, 1, 1)) is False
    assert mc.is_holiday(date(2030, 3, 1)) is True        # 미래연도도 고정 공휴일 인지
