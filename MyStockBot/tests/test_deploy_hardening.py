"""배포 하드닝 — 인증 실패 감속기 · DB 백업 · KIS 연속 실패 경보 · 토큰 상태 노출.

배포 감사에서 나온 High 4건의 회귀 방지:
- 공개 터널 뒤 단일 토큰이 무제한 브루트포스 가능했다 → 실패 기반 전역 감속기.
  (IP별이 아닌 이유: 터널 뒤에서는 모든 요청의 client IP 가 로컬로 보인다.
   락아웃이 아닌 이유: 실패만 세므로 올바른 토큰은 공격 중에도 통과한다.)
- SQLite 백업 전략 부재 → sqlite3 backup API 일일 스냅샷 + 보존 개수.
- KIS 앱키 만료 시 조용한 yfinance 강등 → 연속 실패 임계치에서 알림 채널 경보 1회.
- /api/health 가 데이터 품질 강등을 못 보여줌 → kis_auth.token_status() 노출.
"""
import asyncio
import sqlite3

import pytest
from fastapi import Response
from starlette.requests import Request

import db as db_module
import kis_auth
from server import auth
from server.services import collector


# ────────────────────────────────────────────
# 인증 실패 감속기
#
# TestClient 는 쓰지 않는다 — httpx(최신 starlette 는 httpx2)를 하드 요구하는데
# 런타임 의존성이 아니다(tests/test_alerts_router.py 의 동일 결정 참조).
# 미들웨어를 직접 호출한다 — 감속기 분기는 이 방식이 더 정확히 검증된다.
# ────────────────────────────────────────────

def _request(path="/api/ping", token: str | None = "wrong") -> Request:
    headers = []
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return Request({
        "type": "http", "method": "GET", "path": path,
        "headers": headers, "query_string": b"",
        "scheme": "http", "server": ("test", 80),
    })


async def _pass_through(request):
    return Response(status_code=200)


def _call(path="/api/ping", token: str | None = "wrong") -> Response:
    return asyncio.run(auth.auth_middleware(_request(path, token), _pass_through))


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    monkeypatch.setattr(auth, "_API_TOKEN", "correct-token")
    with auth._fail_lock:
        auth._fail_times.clear()


def test_failures_get_401_until_threshold_then_429():
    for _ in range(auth._FAIL_THRESHOLD):
        assert _call(token="wrong").status_code == 401

    over = _call(token="wrong")
    assert over.status_code == 429
    assert over.headers["Retry-After"] == str(auth._RETRY_AFTER_SECONDS)


def test_valid_token_passes_even_during_bruteforce_storm():
    """감속기는 락아웃이 아니다 — 공격이 몰아쳐도 올바른 토큰은 계속 통과해야 한다."""
    for _ in range(auth._FAIL_THRESHOLD + 5):
        _call(token="wrong")

    assert _call(token="correct-token").status_code == 200


def test_window_expiry_resets_limiter():
    for _ in range(auth._FAIL_THRESHOLD + 1):
        _call(token="wrong")

    # 창(60초)이 지난 것처럼 기존 실패 기록(monotonic)을 과거로 민다
    with auth._fail_lock:
        shifted = [t - auth._FAIL_WINDOW_SECONDS - 1 for t in auth._fail_times]
        auth._fail_times.clear()
        auth._fail_times.extend(shifted)

    assert _call(token="wrong").status_code == 401


def test_health_path_exempt_never_counts():
    """헬스체크는 무인증 예외 — 감속기 카운트에도 잡히면 안 된다(도커가 30초마다 침)."""
    before = len(auth._fail_times)
    assert _call(path="/api/health", token=None).status_code == 200
    assert len(auth._fail_times) == before


# ────────────────────────────────────────────
# DB 백업
# ────────────────────────────────────────────

@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "live.db"))
    db_module.init_db()
    return db_module


def test_create_backup_produces_consistent_snapshot(db, tmp_path):
    db.upsert_candles("005930", "1d", [
        {"t": 1_700_000_000, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10},
    ])
    dest = db.create_backup(backup_dir=str(tmp_path / "backups"))
    assert dest is not None

    conn = sqlite3.connect(dest)
    try:
        n = conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
    finally:
        conn.close()
    assert n == 1


def test_create_backup_retention_prunes_oldest(db, tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    for day in range(1, 6):
        (backup_dir / f"mystockbot-2026010{day}.db").write_bytes(b"x")

    db.create_backup(backup_dir=str(backup_dir), retention=3)

    left = sorted(p.name for p in backup_dir.glob("mystockbot-*.db"))
    assert len(left) == 3
    assert "mystockbot-20260101.db" not in left  # 가장 오래된 것부터 삭제


def test_create_backup_returns_none_when_db_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "no-such.db"))
    assert db_module.create_backup(backup_dir=str(tmp_path / "b")) is None


# ────────────────────────────────────────────
# KIS 연속 실패 경보
# ────────────────────────────────────────────

@pytest.fixture
def alert_spy(monkeypatch):
    """collector 의 경보 발송을 가로챈다 — 채널 둘 다 켜진 것으로 간주."""
    import alert_channels
    sent = []
    monkeypatch.setattr(alert_channels, "discord_enabled", lambda: True)
    monkeypatch.setattr(alert_channels, "slack_enabled", lambda: False)
    monkeypatch.setattr(alert_channels, "send_discord", lambda text, **kw: sent.append(text) or True)
    # 전역 카운터 리셋
    monkeypatch.setattr(collector, "_kis_fail_streak", 0)
    monkeypatch.setattr(collector, "_kis_fail_alerted_at", None)
    return sent


def test_alert_fires_once_at_threshold_and_respects_cooldown(alert_spy):
    for _ in range(collector._KIS_FAIL_ALERT_THRESHOLD - 1):
        collector._note_kis_token_result(False)
    assert alert_spy == []  # 임계치 미만 — 침묵

    collector._note_kis_token_result(False)
    assert len(alert_spy) == 1  # 임계치 도달 — 1회 발송
    assert "KIS 토큰" in alert_spy[0]

    collector._note_kis_token_result(False)
    assert len(alert_spy) == 1  # 쿨다운 내 — 재발송 없음


def test_alert_streak_resets_on_success(alert_spy):
    for _ in range(collector._KIS_FAIL_ALERT_THRESHOLD - 1):
        collector._note_kis_token_result(False)
    collector._note_kis_token_result(True)  # 성공 — 스트릭 리셋
    for _ in range(collector._KIS_FAIL_ALERT_THRESHOLD - 1):
        collector._note_kis_token_result(False)
    assert alert_spy == []


def test_alert_send_failure_does_not_raise(alert_spy, monkeypatch):
    """경보 경로가 죽어도 수집 사이클은 살아야 한다."""
    import alert_channels
    monkeypatch.setattr(alert_channels, "send_discord",
                        lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down")))
    for _ in range(collector._KIS_FAIL_ALERT_THRESHOLD):
        collector._note_kis_token_result(False)  # 예외가 새면 여기서 터진다


# ────────────────────────────────────────────
# 토큰 상태 노출 (/api/health 의 kis 필드 재료)
# ────────────────────────────────────────────

def test_token_status_reflects_success_and_failure(monkeypatch):
    monkeypatch.setattr(kis_auth, "_load_cache", lambda: "tok")
    assert kis_auth.get_token() == "tok"
    assert kis_auth.token_status()["ok"] is True

    monkeypatch.setattr(kis_auth, "_load_cache", lambda: None)
    monkeypatch.delenv("KIS_APP_KEY", raising=False)
    monkeypatch.delenv("KIS_APP_SECRET", raising=False)
    with pytest.raises(kis_auth.MissingCredentialsError):
        kis_auth.get_token()
    status = kis_auth.token_status()
    assert status["ok"] is False
    assert status["detail"]  # 사유가 담긴다


def test_token_status_returns_copy():
    """호출자가 반환 dict 를 변형해도 내부 상태가 오염되면 안 된다."""
    snap = kis_auth.token_status()
    snap["ok"] = "tampered"
    assert kis_auth.token_status()["ok"] != "tampered"
