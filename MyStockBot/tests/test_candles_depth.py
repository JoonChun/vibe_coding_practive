"""차트 과거 깊이 — 페이지네이션·clock-aligned 리샘플·깊이 게이트·before 커서.

## 검증 대상 결함(실측으로 확인된 것들)
① KIS 기간별시세는 호출당 100건 상한인데 단일 호출만 해서 일봉이 ~5개월에서 잘렸다.
② read-through 신선도 게이트가 "신선하면 얕아도 그대로 서빙"이라 얕은 저장소가 고착됐다.
③ 120m/240m positional 리샘플이 재조회마다 다른 t 를 만들어 저장소에 중복 봉을 쌓았다.

DB 는 목이 아니라 tmp_path 의 실제 파일이다 — 저장소 병합·경계 조회(before)·마이그레이션
정리는 목으로는 검증되지 않는다. 외부 소스(KIS HTTP·yfinance)만 monkeypatch 한다.
"""
import pandas as pd
import pytest

import db as db_module
import crawler
from server.services import candles


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "candles.db"))
    db_module.init_db()
    return db_module


@pytest.fixture(autouse=True)
def _reset_candles_memory():
    """candles 모듈의 인메모리 상태(쿨다운·바닥·소스 기억)를 테스트마다 비운다 —
    이전 테스트의 쿨다운이 다음 테스트의 딥 수집을 조용히 막는 오염 방지."""
    with candles._deep_fetch_lock:
        candles._deep_fetch_attempted_at.clear()
    with candles._floor_lock:
        candles._history_floor.clear()
    with candles._source_lock:
        candles._last_source.clear()
    yield


def _daily_item(t: int, price: float = 100.0) -> dict:
    return {"t": t, "open": price, "high": price + 1, "low": price - 1,
            "close": price, "volume": 1000}


_DAY = 86400
# 2024-01-01 00:00 KST 자정 epoch — 일봉 t 의 현실적인 기준점.
_BASE_T = 1704034800


# ────────────────────────────────────────────
# resample_items — clock-aligned 버킷
# ────────────────────────────────────────────

def _minute_items(start_t: int, n: int, step_s: int = 3600) -> list[dict]:
    return [_daily_item(start_t + i * step_s, 100.0 + i) for i in range(n)]


def test_resample_items_clock_aligned_buckets():
    """버킷 t 는 절대 epoch 의 floor — 항상 버킷 크기의 배수다(positional 아님)."""
    start = 7200 * 300_000  # 120분 경계에 정확히 정렬된 기준점
    out = candles.resample_items(_minute_items(start, 5), 120)
    assert [o["t"] % 7200 for o in out] == [0] * len(out)
    assert len(out) == 3  # [봉0,1] [봉2,3] [봉4]
    # OHLCV 합성 규칙: open=첫, close=마지막, high=max, low=min, volume=합
    first = out[0]
    assert first["t"] == start
    assert first["open"] == 100.0 and first["close"] == 101.0
    assert first["high"] == 102.0 and first["volume"] == 2000
    assert out[2]["volume"] == 1000


def test_resample_items_stable_across_shifted_windows():
    """조회창이 밀려도 같은 실제 구간은 같은 버킷 t 로 합성된다 — ③ 오염 결함의 회귀 테스트.
    (positional 방식이면 창 시작이 1시간 밀릴 때 모든 버킷 t 가 달라진다.)"""
    start = _BASE_T + 9 * 3600
    full = _minute_items(start, 8)
    shifted = full[1:]  # 조회창이 한 봉 뒤에서 시작
    t_full = {o["t"] for o in candles.resample_items(full, 240)}
    t_shifted = {o["t"] for o in candles.resample_items(shifted, 240)}
    assert t_shifted <= t_full  # 밀린 창의 버킷은 원래 창 버킷의 부분집합 — 새 t 를 만들지 않는다


def test_resample_items_passthrough_when_unit_leq_1_or_empty():
    items = _minute_items(_BASE_T, 3)
    assert candles.resample_items(items, 1) is items
    assert candles.resample_items([], 120) == []


# ────────────────────────────────────────────
# db — before 커서 조회·오염 행 정리
# ────────────────────────────────────────────

def test_get_candles_store_before_returns_strictly_older(db):
    items = [_daily_item(_BASE_T + i * _DAY) for i in range(10)]
    db.upsert_candles("005930", "1d", items)
    boundary = _BASE_T + 5 * _DAY
    got = db.get_candles_store_before("005930", "1d", 3, boundary)
    assert [g["t"] for g in got] == [_BASE_T + 2 * _DAY, _BASE_T + 3 * _DAY, _BASE_T + 4 * _DAY]
    assert all(g["t"] < boundary for g in got)


def test_init_db_purges_misaligned_resample_rows(db):
    """③ 의 잔재 정리 — 버킷 경계(t % 버킷초 != 0)에 안 맞는 120m/240m 행은 부팅 시
    멱등 삭제되고, 경계에 맞는 행과 다른 tf 는 살아남는다."""
    aligned = 7200 * 1000
    db.upsert_candles("005930", "120m", [_daily_item(aligned), _daily_item(aligned + 3600)])
    db.upsert_candles("005930", "240m", [_daily_item(14400 * 500), _daily_item(14400 * 500 + 3600)])
    db.upsert_candles("005930", "60m", [_daily_item(aligned + 3600)])  # 다른 tf 는 무관

    db.init_db()  # 멱등 — 두 번 불러도 안전

    left_120 = db.get_candles_store("005930", "120m", 10)
    left_240 = db.get_candles_store("005930", "240m", 10)
    assert [r["t"] for r in left_120] == [aligned]
    assert [r["t"] for r in left_240] == [14400 * 500]
    assert len(db.get_candles_store("005930", "60m", 10)) == 1


# ────────────────────────────────────────────
# fetch_kis_ohlcv_paged — 페이지네이션 규칙
# ────────────────────────────────────────────

class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _kis_row(date_str: str) -> dict:
    return {"stck_bsop_date": date_str, "stck_oprc": "100", "stck_hgpr": "110",
            "stck_lwpr": "90", "stck_clpr": "105", "acml_vol": "5000"}


@pytest.fixture(autouse=True)
def _no_throttle(monkeypatch):
    """전역 스로틀 sleep 제거 — 테스트가 0.5초씩 기다리지 않게 한다(호출 여부는 별도 검증)."""
    import kis_auth
    monkeypatch.setattr(kis_auth, "kis_throttle", lambda: None)


def test_paged_accumulates_across_pages_dedup_and_order(monkeypatch):
    """페이지를 역행하며 누적하고, 겹친 날짜는 1건으로, 최종은 날짜 오름차순."""
    pages = [
        [_kis_row("20260810"), _kis_row("20260809"), _kis_row("20260808")],
        [_kis_row("20260808"), _kis_row("20260807")],  # 경계 중복 포함
        [],  # 원천 고갈
    ]
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(dict(params))
        return _FakeResp({"output2": pages[min(len(calls) - 1, len(pages) - 1)]})

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    df = crawler.fetch_kis_ohlcv_paged("005930", "tok", period="D", target_count=100)
    assert list(df["date"]) == ["20260807", "20260808", "20260809", "20260810"]
    # 2페이지의 조회 종료일 = 1페이지 최저 날짜 - 1일
    assert calls[1]["FID_INPUT_DATE_2"] == "20260807"


def test_paged_stops_at_target_count(monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(1)
        # 매 페이지 서로 다른 100일치 — 페이지 번호로 월을 갈라 중복을 없앤다
        month = 12 - len(calls)
        rows = [_kis_row(f"2025{month:02d}{d:02d}") for d in range(28, 0, -1)]
        return _FakeResp({"output2": rows})

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    df = crawler.fetch_kis_ohlcv_paged("005930", "tok", period="D", target_count=50)
    assert len(df) == 50  # 초과분은 최신 50건만
    assert len(calls) == 2  # 28 + 28 = 56 ≥ 50 에서 중단


def test_paged_stops_when_no_progress(monkeypatch):
    """서버가 같은 구간을 반복 반환하면(이상 상황) 무한루프 없이 중단한다."""
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResp({"output2": [_kis_row("20260801")]})

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    df = crawler.fetch_kis_ohlcv_paged("005930", "tok", period="D", target_count=100)
    assert len(df) == 1


def test_paged_respects_end_cursor(monkeypatch):
    """end 를 주면 첫 페이지의 조회 종료일이 그 날짜다 — before 커서의 뿌리."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(dict(params))
        return _FakeResp({"output2": [_kis_row("20230103")]})

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    end = datetime(2023, 1, 15, tzinfo=ZoneInfo("Asia/Seoul"))
    crawler.fetch_kis_ohlcv_paged("005930", "tok", period="D", target_count=10, end=end)
    assert calls[0]["FID_INPUT_DATE_2"] == "20230115"


def test_paged_returns_partial_on_midway_failure(monkeypatch):
    """뒤 페이지 요청이 죽어도 이미 모은 앞 페이지는 살려서 돌려준다."""
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(1)
        if len(calls) >= 2:
            raise ConnectionError("boom")
        return _FakeResp({"output2": [_kis_row("20260810"), _kis_row("20260809")]})

    monkeypatch.setattr(crawler.requests, "get", fake_get)
    df = crawler.fetch_kis_ohlcv_paged("005930", "tok", period="D", target_count=100)
    assert len(df) == 2


# ────────────────────────────────────────────
# get_candles — 깊이 게이트·쿨다운·원천 고갈 바닥
# ────────────────────────────────────────────

def _seed_fresh_shallow(db, code="005930", tf="1d", n=100):
    """저장소를 '신선하지만 얕은' 상태로 만든다 — ② 고착 결함의 전제 조건."""
    db.upsert_candles(code, tf, [_daily_item(_BASE_T + i * _DAY) for i in range(n)])


def test_deep_gate_fetches_when_fresh_but_shallow(db, monkeypatch):
    """② 회귀: 신선해도 요청보다 얕으면 딥 수집이 발동해 저장소가 깊어진다."""
    _seed_fresh_shallow(db, n=100)
    fetched = {}

    def fake_fetch(code, tf, target):
        fetched["target"] = target
        return [_daily_item(_BASE_T - i * _DAY) for i in range(1, 201)], "kis"

    monkeypatch.setattr(candles, "_fetch", fake_fetch)
    res = candles.get_candles("005930", "1d", 300)
    assert fetched["target"] == 300  # 딥 수집은 요청 개수를 목표로 한다
    assert len(res["items"]) == 300  # 기존 100 + 새 200 병합


def test_deep_gate_cooldown_blocks_repeat(db, monkeypatch):
    """딥 수집이 요청을 못 채워도(원천 얕음) 쿨다운 동안은 재수집하지 않는다."""
    _seed_fresh_shallow(db, n=100)
    calls = []

    def fake_fetch(code, tf, target):
        calls.append(target)
        return [_daily_item(_BASE_T + i * _DAY) for i in range(100)], "kis"  # 안 깊어짐

    monkeypatch.setattr(candles, "_fetch", fake_fetch)
    candles.get_candles("005930", "1d", 300)
    candles.get_candles("005930", "1d", 300)  # 쿨다운 내 재요청
    assert len(calls) == 1


def test_deep_gate_history_floor_skips_refetch(db, monkeypatch):
    """딥 수집이 응답을 받고도 못 채우면 바닥을 기억하고, 쿨다운이 풀려도 재수집하지 않는다."""
    _seed_fresh_shallow(db, n=100)
    calls = []

    def fake_fetch(code, tf, target):
        calls.append(target)
        return [_daily_item(_BASE_T + i * _DAY) for i in range(100)], "kis"

    monkeypatch.setattr(candles, "_fetch", fake_fetch)
    candles.get_candles("005930", "1d", 300)
    assert candles._get_history_floor("005930", "1d") == _BASE_T  # 최저 t 가 바닥

    with candles._deep_fetch_lock:
        candles._deep_fetch_attempted_at.clear()  # 쿨다운 해제 시뮬레이션
    candles.get_candles("005930", "1d", 300)
    assert len(calls) == 1  # 바닥 기억이 재수집을 막는다


def test_fresh_and_deep_enough_serves_store_without_fetch(db, monkeypatch):
    _seed_fresh_shallow(db, n=100)

    def explode(*a, **k):
        raise AssertionError("신선+충분한 깊이면 fetch 가 없어야 한다")

    monkeypatch.setattr(candles, "_fetch", explode)
    res = candles.get_candles("005930", "1d", 50)
    assert len(res["items"]) == 50


def test_stale_refresh_with_deep_store_uses_shallow_target(db, monkeypatch):
    """stale 최신화 때 저장소가 이미 깊으면 1페이지 분량(_REFRESH_TARGET)만 갱신한다 —
    매 갱신마다 딥 페이지네이션을 반복하지 않는다."""
    _seed_fresh_shallow(db, n=500)
    monkeypatch.setattr(db_module, "get_candles_age_seconds", lambda c, t: 10_000.0)  # stale
    fetched = {}

    def fake_fetch(code, tf, target):
        fetched["target"] = target
        return [_daily_item(_BASE_T + 499 * _DAY, 200.0)], "kis"

    monkeypatch.setattr(candles, "_fetch", fake_fetch)
    candles.get_candles("005930", "1d", 300)
    assert fetched["target"] == candles._REFRESH_TARGET


# ────────────────────────────────────────────
# get_candles — before 커서
# ────────────────────────────────────────────

def test_before_serves_from_store_when_deep_enough(db, monkeypatch):
    db.upsert_candles("005930", "1d", [_daily_item(_BASE_T + i * _DAY) for i in range(400)])

    def explode(*a, **k):
        raise AssertionError("저장소가 충분하면 외부 호출이 없어야 한다")

    monkeypatch.setattr(candles.kis_auth, "get_token", explode)
    boundary = _BASE_T + 350 * _DAY
    res = candles.get_candles("005930", "1d", 100, before=boundary)
    assert len(res["items"]) == 100
    assert all(it["t"] < boundary for it in res["items"])
    assert res["items"][-1]["t"] == _BASE_T + 349 * _DAY


def test_before_fetches_kis_when_store_shallow_and_sets_floor_on_exhaustion(db, monkeypatch):
    db.upsert_candles("005930", "1d", [_daily_item(_BASE_T + i * _DAY) for i in range(10)])
    monkeypatch.setattr(candles.kis_auth, "get_token", lambda: "tok")
    calls = []

    def fake_paged(code, token, period, target_count, end=None):
        calls.append(end)
        # KIS 가 응답했지만 경계 이전 5일치가 전부(상장 이전 구간 없음)
        base_day = pd.Timestamp(_BASE_T, unit="s", tz="Asia/Seoul")
        dates = [(base_day - pd.Timedelta(days=i)).strftime("%Y%m%d") for i in range(5, 0, -1)]
        return pd.DataFrame([{"date": d, "open": 1, "high": 2, "low": 0, "close": 1, "volume": 10}
                             for d in dates])

    monkeypatch.setattr(candles.crawler, "fetch_kis_ohlcv_paged", fake_paged)

    res = candles.get_candles("005930", "1d", 100, before=_BASE_T)
    assert len(calls) == 1
    assert len(res["items"]) == 5  # 저장소 0 + KIS 5 — 요청(100)에 못 미침 = 원천 고갈
    assert candles._get_history_floor("005930", "1d") == _BASE_T

    # 바닥 이하 재요청은 외부 호출 없이 저장소만
    res2 = candles.get_candles("005930", "1d", 100, before=_BASE_T)
    assert len(calls) == 1
    assert len(res2["items"]) == 5


def test_before_minute_tf_is_store_only(db, monkeypatch):
    """분봉은 어떤 소스도 임의 과거 소급이 안 되므로 before 는 저장소만 본다."""
    hour = 3600
    db.upsert_candles("005930", "60m", [_daily_item(_BASE_T + i * hour) for i in range(20)])

    def explode(*a, **k):
        raise AssertionError("분봉 before 경로는 외부 호출이 없어야 한다")

    monkeypatch.setattr(candles.kis_auth, "get_token", explode)
    res = candles.get_candles("005930", "60m", 5, before=_BASE_T + 10 * hour)
    assert [it["t"] for it in res["items"]] == [_BASE_T + i * hour for i in range(5, 10)]


# ────────────────────────────────────────────
# count 상한 — tf 별
# ────────────────────────────────────────────

@pytest.mark.parametrize("tf, expected", [
    ("1d", 1000), ("1w", 1000), ("60m", 1000), ("120m", 1000), ("240m", 1000),
    ("1m", 300), ("5m", 300), ("1M", 300), ("1y", 300),
])
def test_max_count_per_tf(tf, expected):
    assert candles._max_count_for(tf) == expected
