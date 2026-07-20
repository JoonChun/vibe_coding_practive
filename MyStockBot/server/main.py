# MyStockBot 디렉터리에서 실행: uvicorn server.main:app
# (하위 sys.path 설정이 이 실행 위치를 전제로 함 — 다른 경로에서 실행 시 import 실패)
import logging
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

# kis_ws 등 logging 기반 모듈의 INFO 로그가 보이도록 설정
# (uvicorn 기본 설정은 앱 로거에 핸들러를 붙이지 않아 INFO가 유실됨)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# 다른 src 모듈과 동일 관례: MyStockBot/src, MyStockBot 를 sys.path 에 추가
_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

from dotenv import load_dotenv

load_dotenv(_BASE_DIR / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CORS_ALLOWED_ORIGINS
import db
import stock_master

from .auth import auth_middleware, is_auth_enabled
from .routers import indices, paper, stream, watchlist, snapshot, stocks
from .services import collector, kis_ws, scheduler


def _refresh_stock_master_in_background() -> None:
    """stock_master 가 비었거나 오래됐으면 백그라운드 스레드에서 갱신.

    부팅을 블로킹하지 않는다 — 실패해도 예외를 삼키고 로그만 남긴다(서버는 뜬다).
    """
    try:
        if not stock_master.needs_refresh():
            print("[startup] stock_master 최신 상태 — 갱신 건너뜀")
            return
        print("[startup] stock_master 갱신 필요 — 백그라운드 갱신 시작")
        stock_master.refresh_stock_master()
    except Exception as e:
        print(f"[startup] stock_master 백그라운드 갱신 실패(다음 기회에 재시도): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    threading.Thread(
        target=_refresh_stock_master_in_background, daemon=True, name="stock-master-refresh"
    ).start()
    scheduler.start()
    collector.start()
    try:
        # kis_ws.start()는 내부적으로 재연결·백오프를 자체 관리한다(계약).
        # 그래도 부팅 경로에서 예기치 못한 예외로 서버 자체가 죽는 일은 없어야 하므로
        # 여기서도 한 번 더 격리한다 — 실패해도 REST API/폴링 스냅샷은 정상 동작.
        await kis_ws.start()
    except Exception as e:
        print(f"[startup] KIS 실시간 WS 시작 실패(틱 스트림 비활성, 나머지 기능은 정상 동작): {e}")
    if is_auth_enabled():
        print("API 토큰 인증 활성")
    else:
        print("⚠ API 토큰 미설정 — 인증 비활성")
    yield
    collector.stop()
    scheduler.shutdown()
    try:
        await kis_ws.stop()
    except Exception as e:
        print(f"[shutdown] KIS 실시간 WS 정지 중 예외: {e}")


app = FastAPI(lifespan=lifespan)

# 인증 미들웨어를 CORSMiddleware의 add_middleware 호출보다 먼저 등록한다.
# Starlette는 나중에 add_middleware 된 쪽이 가장 바깥(outermost) 레이어가 되므로,
# 이 순서여야 CORSMiddleware가 최외곽에서 401 응답에도 CORS 헤더를 붙여준다.
# (반대 순서면 인증 미들웨어가 최외곽이 되어, 브라우저가 401 본문 대신 CORS 에러를 본다.)
app.middleware("http")(auth_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    """liveness('status') + readiness(마지막 스냅샷 신선도). 첫 수집 사이클 전이면 ready=false."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from config import TIMEZONE

    from .services import collector

    state = collector.get_state()
    snapshot = None
    if state and state.get("generated_at"):
        snapshot = {"generated_at": state["generated_at"], "items": len(state.get("items", []))}
        try:
            gen = datetime.fromisoformat(state["generated_at"])
            now = datetime.now(gen.tzinfo or ZoneInfo(TIMEZONE))
            snapshot["age_seconds"] = round((now - gen).total_seconds(), 1)
        except (ValueError, TypeError):
            pass
    return {"status": "ok", "ready": snapshot is not None, "snapshot": snapshot}


app.include_router(watchlist.router)
app.include_router(snapshot.router)
app.include_router(stocks.router)
app.include_router(indices.router)
app.include_router(paper.router)
app.include_router(stream.router)
