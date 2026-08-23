"""시장 상태(장전/장중/장마감/휴장) 계산.

`market_calendar` 는 예전부터 있었지만 이를 노출하는 API·UI가 없어 "휴장" 배지의 데이터
근거가 화면에 닿지 않았다(PRD §10.1 블록2 미구현). 여기서 상태 전이와 세션 경계를 고정한다.

특히 잠그는 것:
  · **reference_trading_day** — 지금 보이는 시세가 속한 거래일. 휴장·장전이면 직전 거래일이다.
    이 값이 틀리면 화면이 "최근 거래일 기준" 안내를 잘못 내보내 신선도를 오해시킨다.
  · 장마감·휴장이면 세션 경계가 **다음 거래일**을 가리켜야 한다(카운트다운이 과거를 향하면 안 됨).
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import market_calendar as mc

KST = ZoneInfo("Asia/Seoul")

# 2026-07-24(금)·07-27(월) 은 거래일, 07-25(토)·07-26(일) 은 주말.
_FRI = date(2026, 7, 24)
_SAT = date(2026, 7, 25)
_MON = date(2026, 7, 27)


def _at(d: date, hh: int, mm: int) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=KST)


def test_calendar_assumptions_for_this_test_hold():
    """테스트 전제(어느 날이 거래일인지)가 실제 달력과 맞는지 먼저 확인."""
    assert mc.is_trading_day(_FRI)
    assert not mc.is_trading_day(_SAT)
    assert mc.is_trading_day(_MON)


def test_pre_market():
    s = mc.market_status(_at(_FRI, 8, 30))

    assert s["status"] == "pre"
    assert s["label"] == "장전"
    assert s["session_date"] == "2026-07-24"          # 오늘 세션을 향한다
    assert s["reference_trading_day"] == "2026-07-23"  # 아직 오늘 시세 없음 → 직전 거래일


def test_open_market():
    for hh, mm in [(9, 0), (12, 0), (15, 30)]:
        s = mc.market_status(_at(_FRI, hh, mm))
        assert s["status"] == "open", f"{hh}:{mm}"
        assert s["label"] == "장중"
        assert s["reference_trading_day"] == "2026-07-24"


def test_closed_after_session():
    s = mc.market_status(_at(_FRI, 15, 31))

    assert s["status"] == "closed"
    assert s["label"] == "장마감"
    # 마감 후에는 오늘 종가가 확정 → 기준일은 오늘
    assert s["reference_trading_day"] == "2026-07-24"
    # 카운트다운은 다음 거래일(월요일) 개장을 향해야 한다
    assert s["session_date"] == "2026-07-27"


def test_weekend_is_holiday_and_points_to_next_trading_day():
    s = mc.market_status(_at(_SAT, 12, 0))

    assert s["status"] == "holiday"
    assert s["label"] == "휴장"
    assert s["session_date"] == "2026-07-27"           # 다음 거래일
    assert s["reference_trading_day"] == "2026-07-24"  # 최근 거래일 기준 안내의 근거


def test_public_holiday_is_recognized():
    # 2026-08-15(광복절)은 토요일이므로 평일 공휴일 예시로 개천절(2026-10-03, 토) 대신
    # 큐레이션 표의 평일 공휴일을 쓴다: 2026-09-25(금, 추석 연휴).
    holiday = date(2026, 9, 25)
    assert holiday.weekday() < 5, "이 테스트는 평일 공휴일을 전제로 한다"

    s = mc.market_status(_at(holiday, 11, 0))

    assert s["status"] == "holiday"
    assert s["reference_trading_day"] == "2026-09-23"  # 연휴 직전 거래일


def test_session_boundaries_are_iso_and_ordered():
    s = mc.market_status(_at(_FRI, 10, 0))

    open_dt = datetime.fromisoformat(s["session_open"])
    close_dt = datetime.fromisoformat(s["session_close"])

    assert open_dt < close_dt
    assert open_dt.tzinfo is not None and close_dt.tzinfo is not None
    assert open_dt.time() == mc.SESSION_OPEN
    assert close_dt.time() == mc.SESSION_CLOSE
    # 서버 시각도 tz-aware 로 내려가야 프론트가 시차 없이 카운트다운을 계산한다.
    assert datetime.fromisoformat(s["server_time"]).tzinfo is not None


def test_calendar_covered_flag():
    assert mc.market_status(_at(_FRI, 10, 0))["calendar_covered"] is True
    future = date(mc.TABLE_MAX_YEAR + 1, 3, 3)
    assert mc.market_status(_at(future, 10, 0))["calendar_covered"] is False


def test_previous_and_next_trading_day_skip_long_holidays():
    # 2026 추석 연휴(9/24~9/26) + 주말 → 연휴 전후 거래일로 건너뛰어야 한다.
    assert mc.previous_trading_day(date(2026, 9, 24)) == date(2026, 9, 23)
    assert mc.next_trading_day(date(2026, 9, 24)) == date(2026, 9, 28)


def test_session_times_differ_from_collector_window():
    """수집 창(09:00~15:40)과 표시용 장 시간(09:00~15:30)은 일부러 다르다.

    두 값을 하나로 합치려는 리팩터가 들어오면 이 테스트가 의도를 알려준다.
    """
    from server.services import collector

    assert mc.SESSION_CLOSE < collector._MARKET_CLOSE
