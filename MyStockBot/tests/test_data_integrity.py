"""티어 C — 데이터 정합: 조정 규약·분할 단차·바닥 영속화·상폐 라이프사이클.

이 파일이 잠그는 것들은 전부 "조용히 틀린 데이터가 남는" 종류라, 화면에는 정상처럼
보이면서 판정·백테스트만 오염시킨다. 그래서 목이 아니라 tmp_path 의 실제 SQLite 로
검증한다 — 마이그레이션·PK 충돌·트랜잭션 경계는 목으로는 확인되지 않는다.
"""
from datetime import datetime, timedelta, timezone

import pytest

import db as db_module
from server.services import candles


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "integrity.db"))
    db_module.init_db()
    return db_module


@pytest.fixture(autouse=True)
def _reset_candles_memory():
    """candles 인메모리 상태(L1 바닥 캐시·쿨다운·소스)를 테스트마다 비운다."""
    with candles._deep_fetch_lock:
        candles._deep_fetch_attempted_at.clear()
    with candles._floor_lock:
        candles._history_floor.clear()
    with candles._source_lock:
        candles._last_source.clear()
    yield


_DAY = 86400
_BASE_T = 1704034800  # 2024-01-01 00:00 KST


def _items(n: int, price: float = 100.0, start_t: int = _BASE_T) -> list[dict]:
    return [
        {"t": start_t + i * _DAY, "open": price, "high": price + 1,
         "low": price - 1, "close": price, "volume": 1000}
        for i in range(n)
    ]


# ────────────────────────────────────────────
# 조정 규약(source) 기록·혼합 차단
# ────────────────────────────────────────────

def test_source_is_persisted_and_readable(db):
    db.upsert_candles("005930", "1d", _items(3), source="kis")
    assert db.get_candles_source("005930", "1d") == "kis"


def test_source_none_is_unknown_not_a_lie(db):
    """구버전 경로(source 미지정)는 '규약 불명'이지 'kis'가 아니다."""
    db.upsert_candles("005930", "1d", _items(3))
    assert db.get_candles_source("005930", "1d") is None


def test_switching_source_purges_old_convention(db):
    """KIS(원주가)와 yfinance(조정가)가 같은 종목에 섞이면 기준가가 갈린다 —
    새 소스로 바꿀 때 옛 규약 행을 남기지 않는다."""
    candles.store_candles("005930", "1d", _items(10, price=70_000), "kis")
    assert len(db.get_candles_store("005930", "1d", 100)) == 10

    # 겹치지 않는 과거 구간을 yfinance 로 넣는다 — 퍼지가 없으면 20행이 섞여 남는다.
    candles.store_candles(
        "005930", "1d", _items(5, price=1_400, start_t=_BASE_T - 50 * _DAY), "yfinance"
    )
    stored = db.get_candles_store("005930", "1d", 100)
    assert len(stored) == 5, "옛 규약 행이 남아 기준가가 섞였다"
    assert db.get_candles_source("005930", "1d") == "yfinance"


def test_same_source_does_not_purge(db):
    """같은 규약이면 기존 이력을 유지한 채 병합한다(정상 갱신 경로)."""
    candles.store_candles("005930", "1d", _items(5, start_t=_BASE_T), "kis")
    candles.store_candles("005930", "1d", _items(5, start_t=_BASE_T + 5 * _DAY), "kis")
    assert len(db.get_candles_store("005930", "1d", 100)) == 10


def test_unknown_source_is_filled_not_purged(db):
    """규약 불명(NULL) 행은 퍼지하지 않는다 — 마이그레이션 직후 전 종목을 한 번씩
    날리는 셈이 되고, NULL 행 대부분은 실제로 같은 소스에서 온 것이다.
    새로 쓰는 봉부터 source 가 채워지고, 이후 규약이 실제로 바뀌면 그때 퍼지된다."""
    db.upsert_candles("005930", "1d", _items(10))  # source 없음
    candles.store_candles("005930", "1d", _items(3, start_t=_BASE_T + 50 * _DAY), "kis")

    assert len(db.get_candles_store("005930", "1d", 100)) == 13
    assert db.get_candles_source("005930", "1d") == "kis"


# ────────────────────────────────────────────
# 분할 단차 감지 → 전량 재적재
# ────────────────────────────────────────────

def test_split_step_triggers_full_reload(db):
    """액면분할이 나면 최근 구간만 새 기준가로 덮여 경계 불연속이 영구화됐다 —
    단차를 감지하면 통째로 비우고 새 기준가로만 채운다."""
    candles.store_candles("005930", "1d", _items(10, price=70_000), "kis")

    split = _items(5, price=70_000, start_t=_BASE_T + 10 * _DAY)
    for it in split[2:]:  # 중간에 1/10 분할 단차를 심는다
        it["close"] = it["open"] = it["high"] = it["low"] = 7_000
    candles.store_candles("005930", "1d", split, "kis")

    stored = db.get_candles_store("005930", "1d", 100)
    assert len(stored) == 5, "단차 감지 후에도 옛 기준가 행이 남았다"


def test_normal_volatility_does_not_trigger_reload(db):
    """국내 가격제한(±30%) 안의 정상 급등락은 분할로 오탐하면 안 된다."""
    candles.store_candles("005930", "1d", _items(10, price=70_000), "kis")

    swing = _items(5, price=70_000, start_t=_BASE_T + 10 * _DAY)
    swing[2]["close"] = 89_000   # +27%
    swing[3]["close"] = 66_000   # -26%
    candles.store_candles("005930", "1d", swing, "kis")

    assert len(db.get_candles_store("005930", "1d", 100)) == 15


# ────────────────────────────────────────────
# 원천 고갈 바닥 영속화
# ────────────────────────────────────────────

def test_floor_survives_restart(db):
    """핵심 회귀 — 재시작(L1 캐시 소실) 후에도 바닥이 남아 재수집을 막는다."""
    candles._set_history_floor("005930", "1d", _BASE_T, "kis")

    with candles._floor_lock:  # 프로세스 재시작 흉내 — L1 만 비운다
        candles._history_floor.clear()

    assert candles._get_history_floor("005930", "1d") == _BASE_T


def test_yfinance_floor_is_not_persisted(db):
    """yfinance 폴백(일봉 2년)으로 만든 바닥을 굳히면 그 종목 일봉이 2년에서 영구히
    잘린다 — 메모리에만 남기고 재시작하면 다시 확인하게 둔다."""
    candles._set_history_floor("005930", "1d", _BASE_T, "yfinance")
    assert candles._get_history_floor("005930", "1d") == _BASE_T  # 이번 세션엔 유효

    with candles._floor_lock:
        candles._history_floor.clear()

    assert candles._get_history_floor("005930", "1d") is None


def test_minute_tf_floor_is_not_persisted(db):
    """분봉 '바닥'은 상장 이력이 아니라 yfinance 롤링 창의 부산물이라 기억하면 안 된다."""
    candles._set_history_floor("005930", "60m", _BASE_T, "kis")
    with candles._floor_lock:
        candles._history_floor.clear()
    assert candles._get_history_floor("005930", "60m") is None


def test_floor_only_moves_down(db):
    """더 과거가 확인되면 갱신하되, 위로는 되돌리지 않는다(확인한 깊이를 잃지 않게)."""
    candles._set_history_floor("005930", "1d", _BASE_T, "kis")
    candles._set_history_floor("005930", "1d", _BASE_T + 100 * _DAY, "kis")
    assert db.get_candle_history_floor("005930", "1d") == _BASE_T

    candles._set_history_floor("005930", "1d", _BASE_T - 100 * _DAY, "kis")
    assert db.get_candle_history_floor("005930", "1d") == _BASE_T - 100 * _DAY


def test_stale_floor_is_revalidated(db):
    """바닥은 '더 없다'는 부정 확인이라 스스로 풀리지 않는다 — 한 달 지나면 무시하고
    한 번 재확인하게 둔다(자기잠금 해소)."""
    db.set_candle_history_floor("005930", "1d", _BASE_T, "kis")
    conn = db.get_connection()
    try:
        old = (datetime.now(timezone.utc) - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("UPDATE candle_history_floor SET updated_at = ?", (old,))
        conn.commit()
    finally:
        conn.close()

    assert db.get_candle_history_floor("005930", "1d") is None


def test_purge_forgets_floor(db):
    """캔들을 통째로 비우면 바닥도 거짓이 된다 — 함께 지운다."""
    candles.store_candles("005930", "1d", _items(10, price=70_000), "kis")
    candles._set_history_floor("005930", "1d", _BASE_T, "kis")

    candles.store_candles("005930", "1d", _items(3, price=1_400), "yfinance")  # 규약 전환 퍼지

    assert db.get_candle_history_floor("005930", "1d") is None
    assert candles._get_history_floor("005930", "1d") is None


# ────────────────────────────────────────────
# 상장폐지 라이프사이클
# ────────────────────────────────────────────

_KOSPI = [{"code": f"1{i:05d}", "name": f"코스피{i}", "market": "KOSPI"} for i in range(1200)]
_KOSDAQ = [{"code": f"2{i:05d}", "name": f"코스닥{i}", "market": "KOSDAQ"} for i in range(1200)]


def test_missing_code_is_marked_delisted_and_hidden_from_search(db):
    db.upsert_stock_master(_KOSPI + _KOSDAQ, mark_missing_delisted=True)
    assert db.search_stocks("100000")  # 있다

    # 다음 갱신에서 첫 종목이 빠졌다 = 상장폐지
    db.upsert_stock_master(_KOSPI[1:] + _KOSDAQ, mark_missing_delisted=True)
    assert db.search_stocks("100000") == []


def test_relisted_code_is_restored(db):
    db.upsert_stock_master(_KOSPI + _KOSDAQ, mark_missing_delisted=True)
    db.upsert_stock_master(_KOSPI[1:] + _KOSDAQ, mark_missing_delisted=True)
    assert db.search_stocks("100000") == []

    db.upsert_stock_master(_KOSPI + _KOSDAQ, mark_missing_delisted=True)
    assert db.search_stocks("100000"), "다시 나타난 코드가 복구되지 않았다"


def test_delisted_rows_excluded_from_meta(db):
    """상폐 행이 meta 에 남으면 그 옛 updated_at 이 MIN 에 걸려 부팅마다 마스터를
    다시 받게 된다."""
    db.upsert_stock_master(_KOSPI + _KOSDAQ, mark_missing_delisted=True)
    db.upsert_stock_master(_KOSPI[10:] + _KOSDAQ, mark_missing_delisted=True)
    assert db.get_stock_master_meta()["count"] == len(_KOSPI) - 10 + len(_KOSDAQ)


def test_no_delisting_when_flag_off(db):
    """가드가 막으면(mark_missing_delisted=False) 데이터만 갱신하고 판정은 미룬다."""
    db.upsert_stock_master(_KOSPI + _KOSDAQ, mark_missing_delisted=True)
    db.upsert_stock_master(_KOSPI[1:] + _KOSDAQ, mark_missing_delisted=False)
    assert db.search_stocks("100000"), "판정 보류인데 상폐로 찍혔다"


def test_guard_blocks_truncated_master_file(db):
    """잘린 마스터 파일로 전 종목이 상폐가 되는 것을 막는다 — 이 가드가 이번 변경에서
    가장 위험한 실패를 막는 지점이다."""
    import stock_master

    assert stock_master._delisting_guard_ok(_KOSPI + _KOSDAQ) is True
    # KOSDAQ 이 통째로 비어 옴
    assert stock_master._delisting_guard_ok(_KOSPI) is False
    # 양쪽 다 있지만 절대 하한 미만
    assert stock_master._delisting_guard_ok(_KOSPI[:50] + _KOSDAQ[:50]) is False


def test_guard_blocks_sudden_shrink(db):
    """행 수가 갑자기 5% 넘게 줄면 파일 이상으로 보고 판정을 미룬다."""
    import stock_master

    db.upsert_stock_master(_KOSPI + _KOSDAQ)
    assert stock_master._delisting_guard_ok(_KOSPI + _KOSDAQ) is True
    # 20% 감소 — 실제 상폐로는 나올 수 없는 규모
    shrunk = _KOSPI[:1000] + _KOSDAQ[:920]
    assert stock_master._delisting_guard_ok(shrunk) is False


# ────────────────────────────────────────────
# 고아 캔들 정리
# ────────────────────────────────────────────

def test_removing_watchlist_item_clears_its_candles(db):
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_candles("005930", "1d", _items(10), source="kis")
    db.set_candle_history_floor("005930", "1d", _BASE_T, "kis")

    db.remove_watchlist_item("005930")

    assert db.get_candles_store("005930", "1d", 100) == []
    assert db.get_candle_history_floor("005930", "1d") is None


def test_removal_does_not_touch_other_codes(db):
    """지수 캐시(^KS11)나 다른 종목의 캔들까지 쓸어가면 안 된다."""
    db.add_watchlist_item("005930", "삼성전자")
    db.upsert_candles("005930", "1d", _items(5), source="kis")
    db.upsert_candles("^KS11", "1d", _items(5), source="yfinance")
    db.upsert_candles("000660", "1d", _items(5), source="kis")

    db.remove_watchlist_item("005930")

    assert len(db.get_candles_store("^KS11", "1d", 100)) == 5
    assert len(db.get_candles_store("000660", "1d", 100)) == 5


def test_backoff_prune_drops_removed_codes():
    """관심종목에서 빠진 코드의 백오프 기록이 단조 증가하지 않는다."""
    from server.services import collector

    with collector._fetch_backoff_lock:
        collector._fetch_fail_streak.clear()
        collector._fetch_skip_until.clear()
    collector._note_fetch_failure("000001")
    collector._note_fetch_failure("000002")

    collector._prune_fetch_backoff({"000001"})

    with collector._fetch_backoff_lock:
        assert "000001" in collector._fetch_fail_streak
        assert "000002" not in collector._fetch_fail_streak


def test_delisting_guard_defers_when_count_query_fails(db, monkeypatch):
    """가드가 쓰는 조회가 죽어도 마스터 갱신 전체를 실패시키지 않는다 —
    가드가 목적인데 가드 때문에 데이터 최신화가 막히면 본말전도다."""
    import stock_master

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "count_stock_master", boom)
    assert stock_master._delisting_guard_ok(_KOSPI + _KOSDAQ) is False
