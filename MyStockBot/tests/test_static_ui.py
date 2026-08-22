"""빌드된 웹 UI 서빙 — SPA 폴백과 API 우선순위.

## TestClient 를 쓰지 않는 이유
`fastapi.testclient` 는 httpx 를 하드 요구하고 requirements.txt 에 없다(예전에 그 이유로
CI 가 깨졌다 — tests/test_alerts_router.py 주석 참고). 대신 ASGI 앱을 **직접 호출**한다.
라우팅·정적 서빙은 이 방식으로 충분히, 오히려 정확하게 검증된다.

## 잠그는 계약
  ① 없는 경로는 index.html 로 폴백한다(SPA 클라이언트 라우팅).
  ② `api/` 경로의 404 는 **404 로 남는다.** `/` 마운트에 걸려 HTML 200 이 되면
     "그 엔드포인트가 없다"는 신호가 사라진다 — 실제로 그 404 하나로 원인을 짚은 적이 있다.
  ③ 마운트는 라우터 **뒤**에 등록된다. 앞이면 API 를 전부 가린다.
  ④ 빌드가 없으면 마운트하지 않고 서버는 정상 기동한다.
  ⑤ 경로 트래버설로 dist 밖 파일이 나가지 않는다.
"""
import asyncio

import pytest
from fastapi import FastAPI
from starlette.routing import Mount

from server.static import mount_web_ui

INDEX_MARKER = "<!doctype html><title>ui</title>"
ASSET_MARKER = "console.log(1)"


@pytest.fixture
def dist(tmp_path):
    """최소한의 빌드 산출물."""
    d = tmp_path / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text(INDEX_MARKER, encoding="utf-8")
    (d / "assets" / "app.js").write_text(ASSET_MARKER, encoding="utf-8")
    (d / "sw.js").write_text("// sw", encoding="utf-8")
    # dist 밖의 비밀 파일 — 트래버설로 새면 안 된다.
    (tmp_path / "secret.txt").write_text("SECRET-DO-NOT-SERVE", encoding="utf-8")
    return d


@pytest.fixture
def app(dist):
    a = FastAPI()

    @a.get("/api/ping")
    def ping():
        return {"pong": True}

    # 실제 앱(server/main.py)과 같은 순서 — 라우터 뒤에 마운트.
    mount_web_ui(a, dist)
    return a


def call(app, path: str):
    """ASGI 앱을 직접 호출해 (status, body_text) 를 돌려준다."""
    async def run():
        scope = {
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "path": path, "raw_path": path.encode(),
            "query_string": b"", "headers": [], "scheme": "http",
            "server": ("test", 80), "client": ("t", 1), "root_path": "",
        }
        messages = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            messages.append(message)

        await app(scope, receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = b"".join(
            m.get("body", b"") for m in messages if m["type"] == "http.response.body"
        )
        return start["status"], body.decode("utf-8", errors="replace")

    return asyncio.run(run())


# ── ① SPA 폴백 ──

def test_root_serves_index(app):
    status, body = call(app, "/")
    assert status == 200
    assert INDEX_MARKER in body


@pytest.mark.parametrize("path", ["/paper", "/stocks/005930", "/deep/nested/route"])
def test_client_routes_fall_back_to_index(app, path):
    """새로고침해도 화면이 떠야 한다 — 그 경로의 파일은 존재하지 않는다."""
    status, body = call(app, path)
    assert status == 200
    assert INDEX_MARKER in body


def test_real_assets_are_served_not_index(app):
    status, body = call(app, "/assets/app.js")
    assert status == 200
    assert body == ASSET_MARKER, "실제 파일 대신 index.html 이 나갔다"


# ── ② API 404 는 404 로 ──

@pytest.mark.parametrize("path", ["/api/nope", "/api/alerts/config", "/api"])
def test_api_404_is_not_masked_by_the_spa_fallback(app, path):
    """HTML 200 이 되면 '엔드포인트가 없다'는 진단 신호가 사라진다."""
    status, body = call(app, path)
    assert status == 404, f"{path} 가 SPA 폴백에 걸렸다"
    assert INDEX_MARKER not in body


def test_registered_api_route_still_wins(app):
    status, body = call(app, "/api/ping")
    assert status == 200
    assert '"pong":true' in body.replace(" ", "")


# ── ③ 등록 순서 ──

def test_mount_is_registered_after_api_routes(app):
    """`/` 마운트를 먼저 걸면 API 를 전부 가린다 — 순서를 회귀로 잠근다."""
    mounts = [i for i, r in enumerate(app.routes)
              if isinstance(r, Mount) and r.path == ""]
    api = [i for i, r in enumerate(app.routes)
           if getattr(r, "path", None) == "/api/ping"]

    assert mounts and api, f"라우트를 못 찾았다: {[getattr(r, 'path', r) for r in app.routes]}"
    assert max(api) < min(mounts), "마운트가 API 라우트보다 앞에 등록됐다"


# ── ④ 빌드가 없을 때 ──

def test_missing_build_is_skipped_not_fatal(tmp_path, caplog):
    import logging

    a = FastAPI()
    before = len(a.routes)

    with caplog.at_level(logging.INFO):
        mounted = mount_web_ui(a, tmp_path / "does-not-exist")

    assert mounted is False
    assert len(a.routes) == before, "마운트하지 않아야 한다"
    assert "건너뜁" in caplog.text


def test_directory_without_index_is_skipped(tmp_path):
    d = tmp_path / "dist"
    d.mkdir()
    (d / "stray.txt").write_text("x", encoding="utf-8")

    assert mount_web_ui(FastAPI(), d) is False


def test_mount_returns_true_when_built(dist):
    assert mount_web_ui(FastAPI(), dist) is True


# ── ⑤ 트래버설 ──

@pytest.mark.parametrize("path", [
    "/../secret.txt",
    "/%2e%2e/secret.txt",
    "/assets/../../secret.txt",
])
def test_traversal_never_leaks_files_outside_dist(app, path):
    status, body = call(app, path)
    assert "SECRET-DO-NOT-SERVE" not in body
    # 폴백으로 index.html 이 나가거나 404 — 어느 쪽이든 유출은 아니다.
    assert status in (200, 404)
