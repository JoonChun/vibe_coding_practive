"""KIS 공식 휴장일 조회(CTCA0903R) 파싱 + 캐시 우선 판정 + 1일 1회 호출 제한.

기존 `market_calendar` 는 2026년까지만 큐레이션된 하드코딩 표라 매년 수동 갱신이 필요하고
2027 음력 연휴를 놓친다. 공식 API 캐시를 1순위로 두고 표를 폴백으로 남긴다.

공식 문서가 **"가급적 1일 1회 호출"** 을 요청하므로, 그 제한을 지키는지도 테스트로 잠근다 —
이 제약을 어기면 KIS 원장 서비스에 영향을 준다고 명시돼 있다.
"""
from datetime import date, datetime, timedelta, timezone

import crawler
import market_calendar as mc
from server.services import scheduler


def _holiday_row(bass_dt: str, opnd: str) -> dict:
    """chk_chk_holiday.py COLUMN_MAPPING 의 필드명을 그대로 사용."""
    return {
        "bass_dt": bass_dt,
        "wday_dvsn_cd": "01",
        "bzdy_yn": "Y",
        "tr_day_yn": "Y",
        "opnd_yn": opnd,      # ★ 개장일 여부 — 공식 docstring 이 지정한 필드
        "sttl_day_yn": "Y",
    }


# ── 파싱 ──

def test_parse_uses_opnd_yn():
    rows = [_holiday_row("20270101", "N"), _holiday_row("20270104", "Y")]
    parsed = crawler._parse_kis_holiday_rows(rows)

    assert parsed == [
        {"date": "2027-01-01", "is_open": False},
        {"date": "2027-01-04", "is_open": True},
    ]


def test_parse_skips_malformed_rows():
    rows = [
        _holiday_row("20270104", "Y"),
        _holiday_row("bad-date", "Y"),
        {"bass_dt": "20270105"},                    # opnd_yn 없음
        {**_holiday_row("20270106", "Y"), "opnd_yn": "?"},  # 알 수 없는 값
        _holiday_row("20270107", "N"),
    ]
    parsed = crawler._parse_kis_holiday_rows(rows)

    assert [p["date"] for p in parsed] == ["2027-01-04", "2027-01-07"]


def test_parse_is_case_insensitive_on_flag():
    assert crawler._parse_kis_holiday_rows([_holiday_row("20270104", "y")])[0]["is_open"] is True
    assert crawler._parse_kis_holiday_rows([_holiday_row("20270101", "n")])[0]["is_open"] is False


# ── 연속조회(페이징) ──

class _Resp:
    def __init__(self, rows, tr_cont=""):
        self._rows = rows
        self.headers = {"tr_cont": tr_cont}

    def raise_for_status(self):
        pass

    def json(self):
        return {
            "rt_cd": "0", "output": self._rows,
            "ctx_area_fk": "FK", "ctx_area_nk": "NK",
        }


def test_fetch_follows_continuation_and_dedupes(monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append((headers.get("tr_cont"), params["CTX_AREA_NK"]))
        if not params["CTX_AREA_NK"]:
            return _Resp([_holiday_row("20270104", "Y"), _holiday_row("20270105", "Y")], "M")
        # 두 번째 페이지: 경계 중복 + 신규
        return _Resp([_holiday_row("20270105", "Y"), _holiday_row("20270106", "N")], "")

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    monkeypatch.setattr(crawler.kis_auth, "kis_throttle", lambda: None)

    rows = crawler.fetch_kis_holidays("tok", "20270104", 100)

    assert [r["date"] for r in rows] == ["2027-01-04", "2027-01-05", "2027-01-06"]
    # 첫 요청은 tr_cont 빈 값, 연속 요청은 "N" + 앞 응답의 ctx 를 되돌려준다
    assert calls[0] == ("", "")
    assert calls[1] == ("N", "NK")


def test_fetch_stops_at_max_days(monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _Resp([_holiday_row(f"2027010{i}", "Y") for i in range(1, 6)], "M")

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    monkeypatch.setattr(crawler.kis_auth, "kis_throttle", lambda: None)

    rows = crawler.fetch_kis_holidays("tok", "20270101", 3)

    assert len(rows) == 3


def test_fetch_returns_empty_on_http_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("timeout")

    monkeypatch.setattr(crawler.requests, "get", boom)
    monkeypatch.setattr(crawler.kis_auth, "kis_throttle", lambda: None)

    assert crawler.fetch_kis_holidays("tok", "20270101", 100) == []


def test_fetch_tolerates_single_object_output(monkeypatch):
    class _Single(_Resp):
        def json(self):
            return {"rt_cd": "0", "output": _holiday_row("20270104", "Y")}

    monkeypatch.setattr(crawler.requests, "get", lambda *a, **k: _Single([]))
    monkeypatch.setattr(crawler.kis_auth, "kis_throttle", lambda: None)

    rows = crawler.fetch_kis_holidays("tok", "20270104", 100)
    assert rows == [{"date": "2027-01-04", "is_open": True}]


# ── 캐시 우선 판정 ──

def test_cache_overrides_builtin_table(monkeypatch):
    """공식 캐시가 있으면 하드코딩 표보다 우선한다 — 표에 없는 음력 연휴를 잡는 핵심."""
    # 2027-02-08(월)은 하드코딩 표에 없으니 표만으로는 '거래일'로 판정된다.
    target = date(2027, 2, 8)
    assert target.weekday() < 5 and not mc.is_holiday(target)

    monkeypatch.setattr(mc, "_cached_open_flag", lambda d: False if d == target else None)

    assert mc.is_trading_day(target) is False
    assert mc.calendar_source(target) == "kis"


def test_cache_can_also_mark_a_day_open(monkeypatch):
    """표가 휴장이라 해도 공식 캐시가 개장이라면 개장이다(임시 개장·표 오류 대응)."""
    target = date(2026, 5, 5)  # 표상 어린이날 → 휴장
    assert mc.is_holiday(target)

    monkeypatch.setattr(mc, "_cached_open_flag", lambda d: True)

    assert mc.is_trading_day(target) is True


def test_falls_back_to_builtin_when_cache_missing(monkeypatch):
    monkeypatch.setattr(mc, "_cached_open_flag", lambda d: None)

    assert mc.is_trading_day(date(2026, 7, 24)) is True     # 평일
    assert mc.is_trading_day(date(2026, 7, 25)) is False    # 토요일
    assert mc.is_trading_day(date(2026, 9, 25)) is False    # 표상 추석 연휴
    assert mc.calendar_source(date(2026, 7, 24)) == "builtin"


def test_cache_lookup_never_raises(monkeypatch):
    """DB 가 없거나 깨져도 달력은 동작해야 한다(크론 러너에는 DB가 비어 있다)."""
    import db

    def boom(_date_str):
        raise RuntimeError("no such table")

    monkeypatch.setattr(db, "get_market_open_flag", boom)

    assert mc._cached_open_flag(date(2026, 7, 24)) is None
    assert mc.is_trading_day(date(2026, 7, 24)) is True


def test_market_status_reports_calendar_source(monkeypatch):
    from zoneinfo import ZoneInfo

    monkeypatch.setattr(mc, "_cached_open_flag", lambda d: True)
    s = mc.market_status(datetime(2027, 3, 3, 10, 0, tzinfo=ZoneInfo("Asia/Seoul")))

    assert s["calendar_source"] == "kis"
    # 표 범위(2026) 밖이지만 공식 캐시가 있으므로 신뢰 가능으로 표시한다.
    assert s["calendar_covered"] is True
    assert s["status"] == "open"


# ── 1일 1회 호출 제한 ──

def test_refresh_skips_when_recently_fetched(monkeypatch):
    """공식 문서가 요청한 '1일 1회'를 코드로 지킨다 — 최근 조회면 호출조차 하지 않는다."""
    import db

    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db, "get_market_holiday_meta", lambda: {"fetched_at": recent})

    called = []
    monkeypatch.setattr(crawler, "fetch_kis_holidays", lambda *a: called.append(a) or [])

    result = scheduler.refresh_market_holidays()

    assert result["called"] is False
    assert called == [], "1일 1회 제한을 무시하고 호출했다"
    assert "건너뜀" in result["reason"]


def test_refresh_proceeds_when_cache_is_old(monkeypatch):
    import db
    import kis_auth

    old = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db, "get_market_holiday_meta", lambda: {"fetched_at": old})
    monkeypatch.setattr(kis_auth, "get_token", lambda: "tok")
    monkeypatch.setattr(
        crawler, "fetch_kis_holidays",
        lambda *a: [{"date": "2027-01-04", "is_open": True}],
    )
    saved = []
    monkeypatch.setattr(db, "upsert_market_holidays", lambda rows: saved.extend(rows) or len(rows))

    result = scheduler.refresh_market_holidays()

    assert result["called"] is True
    assert result["saved"] == 1
    assert saved == [{"date": "2027-01-04", "is_open": True}]


def test_refresh_without_credentials_is_graceful(monkeypatch):
    import db
    import kis_auth

    monkeypatch.setattr(db, "get_market_holiday_meta", lambda: {"fetched_at": None})

    def no_token():
        raise RuntimeError("KIS_APP_KEY 없음")

    monkeypatch.setattr(kis_auth, "get_token", no_token)

    result = scheduler.refresh_market_holidays()

    assert result["called"] is False
    assert result["saved"] == 0
    assert "자격증명" in result["reason"]


def test_refresh_empty_result_keeps_existing_cache(monkeypatch):
    """조회 실패로 빈 결과가 와도 기존 캐시를 덮어써 지우지 않는다."""
    import db
    import kis_auth

    monkeypatch.setattr(db, "get_market_holiday_meta", lambda: {"fetched_at": None})
    monkeypatch.setattr(kis_auth, "get_token", lambda: "tok")
    monkeypatch.setattr(crawler, "fetch_kis_holidays", lambda *a: [])

    upserts = []
    monkeypatch.setattr(db, "upsert_market_holidays", lambda rows: upserts.append(rows))

    result = scheduler.refresh_market_holidays()

    assert result["saved"] == 0
    assert upserts == [], "빈 결과로 캐시를 건드렸다"


def test_force_bypasses_the_interval(monkeypatch):
    import db
    import kis_auth

    recent = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    monkeypatch.setattr(db, "get_market_holiday_meta", lambda: {"fetched_at": recent})
    monkeypatch.setattr(kis_auth, "get_token", lambda: "tok")
    monkeypatch.setattr(
        crawler, "fetch_kis_holidays", lambda *a: [{"date": "2027-01-04", "is_open": True}]
    )
    monkeypatch.setattr(db, "upsert_market_holidays", lambda rows: len(rows))

    assert scheduler.refresh_market_holidays(force=True)["called"] is True
