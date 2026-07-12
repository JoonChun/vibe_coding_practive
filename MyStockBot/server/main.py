# MyStockBot 디렉터리에서 실행: uvicorn server.main:app
# (하위 sys.path 설정이 이 실행 위치를 전제로 함 — 다른 경로에서 실행 시 import 실패)
import sys
from contextlib import asynccontextmanager
from pathlib import Path

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

from .auth import auth_middleware, is_auth_enabled
from .routers import watchlist, snapshot
from .services import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler.start()
    if is_auth_enabled():
        print("API 토큰 인증 활성")
    else:
        print("⚠ API 토큰 미설정 — 인증 비활성")
    yield
    scheduler.shutdown()


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
    return {"status": "ok"}


app.include_router(watchlist.router)
app.include_router(snapshot.router)
