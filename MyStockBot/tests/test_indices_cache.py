"""지수 캐시 — 실패를 성공과 같은 수명으로 붙잡지 않는다.

## 무엇이 틀렸었나
예전 구현은 두 지수를 한 리스트로 묶어 캐시하고 **실패 항목도 성공과 같은 TTL(60초)로**
저장했다. 결과:
  · 순간 장애 하나가 "데이터 없음" 화면을 60초 고정시켰다. 네트워크가 1초 뒤 복구돼도
    남은 59초는 새로고침해도 캐시가 실패를 응답했다.
  · 실패가 직전의 성공 값을 밀어냈다 — 되돌릴 값이 있는데도 버렸다.

여기서 잠그는 계약:
  ① 성공은 INDICES_CACHE_TTL_SECONDS 동안 재사용된다.
  ② 실패는 INDICES_ERROR_RETRY_SECONDS 만 지나면 다시 조회한다(성공 TTL 보다 짧다).
  ③ 실패는 직전 성공 값을 지우지 않고, 그 값을 stale=True 로 내준다.
  ④ 너무 낡은 값(INDICES_STALE_MAX_SECONDS 초과)은 stale 로도 내주지 않는다.
  ⑤ 한 지수의 신선도가 다른 지수의 재조회를 막지 않는다.
"""
import pytest

from server.services import indices


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    """테스트 간 캐시가 새지 않도록 매번 빈 dict 로 교체."""
    monkeypatch.setattr(indices, "_cache", {})


@pytest.fixture
def clock(monkeypatch):
    """monotonic 을 손으로 돌린다 — sleep 없이 TTL 경과를 검증한다."""
    holder = {"t": 1000.0}
    monkeypatch.setattr(indices.time, "monotonic", lambda: holder["t"])
    return holder


class Source:
    """_fetch_one 대역. 호출 수를 세고, 원할 때 실패로 전환한다."""

    def __init__(self, value=2600.0):
        self.calls = 0
        self.failing = False
        self.value = value

    def __call__(self, definition):
        self.calls += 1
        if self.failing:
            raise RuntimeError("조회 실패")
        return self.value, 5.0, 0.19, None, "kis"


@pytest.fixture
def source(monkeypatch):
    s = Source()
    monkeypatch.setattr(indices, "_fetch_one", s)
    return s


def _by_code(result):
    return {it["code"]: it for it in result["items"]}


# ── ① 성공 캐시 ──

def test_success_is_reused_within_ttl(clock, source, monkeypatch):
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)

    indices.get_indices()
    assert source.calls == len(indices._INDEX_DEFS)

    clock["t"] += 59
    result = indices.get_indices()

    assert source.calls == len(indices._INDEX_DEFS), "TTL 안인데 재조회했다"
    assert result["cache_hit"] is True
    assert all(it["stale"] is False for it in result["items"])


def test_success_is_refetched_after_ttl(clock, source, monkeypatch):
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)

    indices.get_indices()
    clock["t"] += 61
    result = indices.get_indices()

    assert source.calls == 2 * len(indices._INDEX_DEFS)
    assert result["cache_hit"] is False


# ── ② 실패는 짧게만 붙잡는다 (핵심 회귀) ──

def test_failure_is_retried_long_before_success_ttl(clock, source, monkeypatch):
    """이것이 원래 결함이다 — 실패가 60초 눌러앉아 복구를 가렸다."""
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)

    source.failing = True
    first = _by_code(indices.get_indices())
    assert first["KOSPI"]["error"] is not None
    assert first["KOSPI"]["value"] is None
    calls_after_failure = source.calls

    # 성공 TTL(60초) 안이지만 실패 재시도 간격(10초)은 지났다 → 다시 조회해야 한다.
    clock["t"] += 11
    source.failing = False
    second = _by_code(indices.get_indices())

    assert source.calls > calls_after_failure, "실패를 성공과 같은 TTL 로 붙잡았다"
    assert second["KOSPI"]["error"] is None
    assert second["KOSPI"]["value"] == 2600.0
    assert second["KOSPI"]["stale"] is False


def test_failure_is_not_hammered_every_request(clock, source, monkeypatch):
    """반대 방향 — 실패해도 매 요청 재조회하지는 않는다(재시도 간격 안에서는 재사용)."""
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)

    source.failing = True
    indices.get_indices()
    calls = source.calls

    clock["t"] += 5
    indices.get_indices()

    assert source.calls == calls


def test_error_retry_never_exceeds_success_ttl(clock, source, monkeypatch):
    """설정을 거꾸로 줘도 실패가 성공보다 오래 붙잡히지 않는다."""
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 30)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 9999)

    source.failing = True
    indices.get_indices()
    calls = source.calls

    clock["t"] += 31
    indices.get_indices()

    assert source.calls > calls


# ── ③ 실패가 직전 성공 값을 지우지 않는다 ──

def test_failure_serves_last_good_value_as_stale(clock, source, monkeypatch):
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)
    monkeypatch.setattr(indices, "INDICES_STALE_MAX_SECONDS", 900)

    indices.get_indices()          # 성공 1회 → good 확보

    clock["t"] += 61
    source.failing = True
    item = _by_code(indices.get_indices())["KOSPI"]

    assert item["value"] == 2600.0, "되돌릴 성공 값이 있는데 버렸다"
    assert item["stale"] is True
    assert item["error"] is not None, "낡음의 이유가 사라졌다"
    assert item["stale_age_seconds"] == pytest.approx(61, abs=1)


def test_repeated_failures_keep_the_same_good_value(clock, source, monkeypatch):
    """실패가 반복돼도 good 을 계속 승계한다(중간에 잃어버리지 않는다)."""
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)
    monkeypatch.setattr(indices, "INDICES_STALE_MAX_SECONDS", 900)

    indices.get_indices()
    source.failing = True
    clock["t"] += 61          # 성공 TTL 을 먼저 넘겨야 재조회(=첫 실패)가 일어난다

    for _ in range(5):
        item = _by_code(indices.get_indices())["KOSPI"]
        assert item["value"] == 2600.0
        assert item["stale"] is True
        clock["t"] += 11      # 실패 재시도 간격을 넘겨 다음 시도를 유도


def test_recovery_clears_stale(clock, source, monkeypatch):
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)

    indices.get_indices()
    clock["t"] += 61
    source.failing = True
    indices.get_indices()

    clock["t"] += 11
    source.failing = False
    source.value = 2700.0
    item = _by_code(indices.get_indices())["KOSPI"]

    assert (item["value"], item["stale"], item["error"]) == (2700.0, False, None)
    assert item["stale_age_seconds"] is None


# ── ④ 너무 낡은 값은 내주지 않는다 ──

def test_value_older_than_stale_max_is_not_served(clock, source, monkeypatch):
    """몇 시간 전 지수를 현재값처럼 보여주는 것은 "데이터 없음"보다 나쁘다."""
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)
    monkeypatch.setattr(indices, "INDICES_STALE_MAX_SECONDS", 300)

    indices.get_indices()
    clock["t"] += 301
    source.failing = True
    item = _by_code(indices.get_indices())["KOSPI"]

    assert item["value"] is None
    assert item["stale"] is False
    assert item["error"] is not None


# ── ⑤ 지수별 독립 ──

def test_one_index_freshness_does_not_block_the_other(clock, monkeypatch):
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)

    calls = {"KOSPI": 0, "KOSDAQ": 0}

    def fetch(definition):
        calls[definition["code"]] += 1
        if definition["code"] == "KOSDAQ" and calls["KOSDAQ"] == 1:
            raise RuntimeError("코스닥 첫 시도 실패")
        return 2600.0, 5.0, 0.19, None, "kis"

    monkeypatch.setattr(indices, "_fetch_one", fetch)

    indices.get_indices()
    assert calls == {"KOSPI": 1, "KOSDAQ": 1}

    # 코스피는 아직 신선(60초), 코스닥은 실패라 재시도 대상(10초).
    clock["t"] += 11
    result = indices.get_indices()

    assert calls == {"KOSPI": 1, "KOSDAQ": 2}, "실패한 쪽만 재조회해야 한다"
    assert result["cache_hit"] is False
    by_code = _by_code(result)
    assert by_code["KOSPI"]["error"] is None
    assert by_code["KOSDAQ"]["error"] is None


# ── 스키마 일관성 ──

def test_all_render_paths_have_identical_keys(clock, source, monkeypatch):
    """성공·stale·완전실패 세 경로의 키가 같아야 프론트가 균일하게 다룬다."""
    monkeypatch.setattr(indices, "INDICES_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(indices, "INDICES_ERROR_RETRY_SECONDS", 10)
    monkeypatch.setattr(indices, "INDICES_STALE_MAX_SECONDS", 300)

    ok = _by_code(indices.get_indices())["KOSPI"]

    clock["t"] += 61
    source.failing = True
    stale = _by_code(indices.get_indices())["KOSPI"]

    clock["t"] += 301
    dead = _by_code(indices.get_indices())["KOSPI"]

    assert stale["stale"] is True and dead["stale"] is False
    assert set(ok) == set(stale) == set(dead)


def test_response_matches_the_declared_schema(clock, source):
    """추가한 필드가 응답 모델과 어긋나면 실서버에서만 터진다 — 여기서 검증한다."""
    from server.schemas import IndicesResponse

    source.failing = True
    IndicesResponse.model_validate(indices.get_indices())

    source.failing = False
    clock["t"] += 9999
    validated = IndicesResponse.model_validate(indices.get_indices())
    assert validated.items[0].stale is False
