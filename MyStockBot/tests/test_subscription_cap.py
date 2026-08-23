"""KIS 세션 구독 한도(41건) 초과 가시화.

## 왜 필요한가
watchlist 는 추가 순(ORDER BY w.id)이라, 41건을 넘기면 **가장 최근에 추가한 종목**이
잘린다 — 사용자가 방금 넣은, 제일 관심 있는 종목이 정확히 실시간에서 빠지는 구조다.
예전에는 그 사실이 서버 로그 warning 한 줄로만 남아, 화면의 실시간 배지는 초록인데
그 종목만 영원히 틱이 오지 않았다.

여기서 잠그는 계약 두 가지:
  ① get_status() 가 excluded/subscription_limit 을 실어 보낸다(프론트가 표시할 근거).
  ② 제외 목록이 바뀌면 **미연결 상태에서도** status 를 브로드캐스트한다 — 예전에는
     조기 return 뒤에 브로드캐스트가 없어, 42번째 종목을 추가해도 이미 열려 있는
     탭은 새로고침 전까지 아무것도 몰랐다.
"""
import asyncio

import pytest

import db as db_module
from server.services import kis_ws


@pytest.fixture(autouse=True)
def _reset_module_state(monkeypatch):
    """모듈 전역(_target_codes·_excluded_codes·_ws·_connected)을 테스트마다 초기화."""
    monkeypatch.setattr(kis_ws, "_target_codes", [])
    monkeypatch.setattr(kis_ws, "_excluded_codes", [])
    monkeypatch.setattr(kis_ws, "_ws", None)
    monkeypatch.setattr(kis_ws, "_connected", False)
    yield


def _watchlist(n: int) -> list[dict]:
    """활성 관심종목 n개. 코드는 추가 순 — 뒤쪽이 '최근 추가'다."""
    return [{"code": f"{i:06d}", "name": f"종목{i}"} for i in range(1, n + 1)]


def _run_refresh(monkeypatch, n: int) -> list[dict]:
    """watchlist n개로 _refresh_subscriptions 를 1회 돌리고, 브로드캐스트된 프레임 목록 반환."""
    monkeypatch.setattr(db_module, "load_watchlist", lambda: _watchlist(n))

    broadcasts: list[dict] = []

    async def fake_broadcast(event: dict) -> None:
        broadcasts.append(event)

    monkeypatch.setattr(kis_ws, "_broadcast", fake_broadcast)
    asyncio.run(kis_ws._refresh_subscriptions())
    return broadcasts


# ────────────────────────────────────────────
# get_status 계약
# ────────────────────────────────────────────

def test_status_exposes_excluded_and_limit(monkeypatch):
    _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS + 3)

    status = kis_ws.get_status()
    assert status["subscription_limit"] == kis_ws._MAX_SUBSCRIPTIONS
    assert len(status["subscribed"]) == kis_ws._MAX_SUBSCRIPTIONS
    # 잘린 3개는 '가장 최근에 추가한' 뒤쪽 3개여야 한다 — 이게 이 결함의 핵심이다.
    assert status["excluded"] == ["000042", "000043", "000044"]


def test_status_keeps_legacy_keys(monkeypatch):
    """기존 계약(kis_connected·subscribed)은 그대로 — 구버전 프론트가 깨지면 안 된다."""
    _run_refresh(monkeypatch, 3)
    status = kis_ws.get_status()
    assert set(status) >= {"kis_connected", "subscribed"}
    assert status["subscribed"] == ["000001", "000002", "000003"]


def test_no_exclusion_under_limit(monkeypatch):
    _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS)
    assert kis_ws.get_status()["excluded"] == []


def test_exclusion_clears_when_back_under_limit(monkeypatch):
    """한도 아래로 내려오면 반드시 비워야 한다 — 안 그러면 경고가 영구히 남는다."""
    _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS + 2)
    assert kis_ws.get_status()["excluded"] != []

    _run_refresh(monkeypatch, 5)
    assert kis_ws.get_status()["excluded"] == []


# ────────────────────────────────────────────
# 브로드캐스트 — 미연결 상태에서도 나가야 한다
# ────────────────────────────────────────────

def test_broadcasts_status_when_exclusion_appears_even_while_disconnected(monkeypatch):
    """_ws=None(미연결)이어도 제외 목록 변화는 알린다 — 조기 return 앞에 있어야 한다."""
    broadcasts = _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS + 1)

    status_frames = [b for b in broadcasts if b.get("type") == "status"]
    assert len(status_frames) == 1
    assert status_frames[0]["excluded"] == ["000042"]


def test_broadcasts_again_when_exclusion_clears(monkeypatch):
    _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS + 1)
    broadcasts = _run_refresh(monkeypatch, 3)

    status_frames = [b for b in broadcasts if b.get("type") == "status"]
    assert len(status_frames) == 1
    assert status_frames[0]["excluded"] == []


def test_no_broadcast_when_exclusion_unchanged(monkeypatch):
    """제외 목록이 그대로면 60초마다 같은 프레임을 쏘지 않는다."""
    _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS + 1)
    broadcasts = _run_refresh(monkeypatch, kis_ws._MAX_SUBSCRIPTIONS + 1)

    assert [b for b in broadcasts if b.get("type") == "status"] == []
