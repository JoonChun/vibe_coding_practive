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


def test_lunar_holiday_in_curated_year():
    # 2026 추석 연휴(9/24~9/26) — 큐레이션된 연도는 음력 연휴까지 인지해야 한다.
    assert mc.is_trading_day(date(2026, 9, 24)) is False
    assert mc.is_trading_day(date(2026, 9, 25)) is False


def test_year_coverage_boundary():
    # 표 범위 안/밖을 구분해야 호출부가 "달력만 믿지 말라"는 경고를 낼 수 있다.
    assert mc.is_year_covered(date(mc.TABLE_MAX_YEAR, 12, 31)) is True
    assert mc.is_year_covered(date(mc.TABLE_MAX_YEAR + 1, 1, 2)) is False
    assert mc.is_year_covered(f"{mc.TABLE_MAX_YEAR + 1}-03-02") is False
