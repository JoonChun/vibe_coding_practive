# MyStockBot 디렉터리에서 실행: uvicorn server.main:app
# (하위 sys.path 설정이 이 실행 위치를 전제로 함 — 다른 경로에서 실행 시 import 실패)
import logging
import sqlite3
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

# 앱 로거의 INFO 로그가 보이도록 설정 (uvicorn 기본 설정은 앱 로거에 핸들러를 붙이지 않아
# INFO 가 유실됨). 타임스탬프·레벨·로거명을 포함해 운영 진단이 가능하게 한다 — 이전에는
# 모듈마다 print() 가 섞여 있어 언제 어느 모듈에서 난 로그인지 알 수 없었다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)

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
import watchlist_sync

from .auth import auth_middleware, is_auth_enabled
from .errors import sqlite_operational_error_handler
from .static import mount_web_ui
from .routers import alerts, indices, market, paper, stream, watchlist, snapshot, stocks
from .services import collector, kis_ws, scheduler, tick_aggregator

logger = logging.getLogger(__name__)


def _refresh_stock_master_in_background() -> None:
    """stock_master 가 비었거나 오래됐으면 백그라운드 스레드에서 갱신.

    부팅을 블로킹하지 않는다 — 실패해도 예외를 삼키고 로그만 남긴다(서버는 뜬다).
    """
    try:
        if not stock_master.needs_refresh():
            logger.info("[startup] stock_master 최신 상태 — 갱신 건너뜀")
            return
        logger.info("[startup] stock_master 갱신 필요 — 백그라운드 갱신 시작")
        stock_master.refresh_stock_master()
    except Exception as e:
        logger.warning("[startup] stock_master 백그라운드 갱신 실패(다음 기회에 재시도): %s", e)


def _refresh_holidays_in_background() -> None:
    """휴장일 캐시를 부팅 시 1회 시도(내부에서 20시간 제한을 재확인해 과호출을 막는다).

    자격증명이 없으면 조용히 건너뛰고 하드코딩 표로 계속 동작한다.
    """
    try:
        result = scheduler.refresh_market_holidays()
        if result["called"] and result["saved"]:
            logger.info("[startup] 휴장일 캐시 %d건 확보", result["saved"])
        else:
            logger.info("[startup] 휴장일 캐시 갱신 건너뜀: %s", result["reason"])
    except Exception as e:
        logger.warning("[startup] 휴장일 캐시 갱신 실패(스케줄러가 재시도): %s", e)


def _import_watchlist_from_sheet_in_background() -> None:
    """시트 Dashboard 에만 있는 관심종목을 앱으로 끌어온다(부팅 시 1회, 추가 전용).

    자격증명·SPREADSHEET_ID 가 없으면 조용히 비활성(웹앱 단독 구성 지원).
    """
    try:
        if not watchlist_sync.is_enabled():
            logger.info("[startup] 관심종목 시트 동기화 비활성(자격증명/SPREADSHEET_ID 없음)")
            return
        result = watchlist_sync.import_from_sheet()
        logger.info(
            "[startup] 관심종목 시트 임포트: 추가 %d건 / 기존 %d건 (시트 %d건)",
            result["added"], result["skipped"], result["sheet_items"],
        )
    except Exception as e:
        logger.warning("[startup] 관심종목 시트 임포트 실패(스케줄러가 재시도): %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    threading.Thread(
        target=_refresh_stock_master_in_background, daemon=True, name="stock-master-refresh"
    ).start()
    threading.Thread(
        target=_import_watchlist_from_sheet_in_background,
        daemon=True,
        name="watchlist-sheet-import",
    ).start()
    threading.Thread(
        target=_refresh_holidays_in_background, daemon=True, name="holiday-refresh"
    ).start()
    scheduler.start()
    collector.start()
    try:
        # kis_ws.start()는 내부적으로 재연결·백오프를 자체 관리한다(계약).
        # 그래도 부팅 경로에서 예기치 못한 예외로 서버 자체가 죽는 일은 없어야 하므로
        # 여기서도 한 번 더 격리한다 — 실패해도 REST API/폴링 스냅샷은 정상 동작.
        await kis_ws.start()
        # tick_aggregator 는 자체 큐로 kis_ws.add_listener 를 등록하므로 kis_ws.start()
        # **이후**에 기동해야 한다. 실패해도 나머지 기능은 정상 동작한다(실시간 참고
        # 판정과 진행중 봉만 비활성).
        await tick_aggregator.start()
    except Exception as e:
        logger.warning(
            "[startup] KIS 실시간 WS 시작 실패(틱 스트림 비활성, 나머지 기능은 정상 동작): %s", e
        )
    if is_auth_enabled():
        logger.info("[startup] API 토큰 인증 활성")
    else:
        logger.warning("[startup] ⚠ API 토큰 미설정 — 인증 비활성")
    yield
    collector.stop()
    scheduler.shutdown()
    try:
        await tick_aggregator.stop()
        await kis_ws.stop()
    except Exception as e:
        logger.warning("[shutdown] KIS 실시간 WS 정지 중 예외: %s", e)


app = FastAPI(lifespan=lifespan)

# 인증 미들웨어를 CORSMiddleware의 add_middleware 호출보다 먼저 등록한다.
# Starlette는 나중에 add_middleware 된 쪽이 가장 바깥(outermost) 레이어가 되므로,
# 이 순서여야 CORSMiddleware가 최외곽에서 401 응답에도 CORS 헤더를 붙여준다.
# (반대 순서면 인증 미들웨어가 최외곽이 되어, 브라우저가 401 본문 대신 CORS 에러를 본다.)
app.middleware("http")(auth_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    # 프론트가 실제로 쓰는 것만 허용한다(web/src/api.ts 기준: 조회는 GET, 관심종목
    # 추가·주문·알림테스트는 POST, 관심종목 삭제는 DELETE). OPTIONS 는 preflight 용.
    # 토큰 인증이 앞단에 있어 "*" 라도 실질 위험은 낮지만, 허용 범위를 실제 사용면에
    # 맞춰 두면 나중에 늘어난 메서드가 조용히 통과하지 않는다.
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    # Authorization(토큰) + Content-Type(JSON 본문) + ngrok 경고 우회 헤더.
    # 마지막 것은 api.ts 가 모든 요청에 붙이므로 빠지면 preflight 가 막힌다.
    allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning"],
)

# SQLite 쓰기 경합(busy_timeout 초과)을 500 대신 429 + Retry-After 로 바꾼다.
# 하위 클래스까지 잡히도록 OperationalError 에 등록한다(Starlette 는 MRO 로 조회한다).
# 경합이 아닌 OperationalError 는 핸들러가 다시 던져 기존처럼 500 이 된다.
app.add_exception_handler(sqlite3.OperationalError, sqlite_operational_error_handler)


@app.get("/api/health")
def health():
    """liveness('status') + readiness(마지막 스냅샷 신선도). 첫 수집 사이클 전이면 ready=false.

    kis: 마지막 KIS 토큰 발급 시도 결과. ok=false 가 지속되면 앱키 만료/폐기로 전
    종목이 yfinance 지연 데이터로 조용히 강등된 상태다 — 외부 모니터링(uptime 체커)이
    이 필드를 보고 경보를 걸 수 있다(status 는 그 경우에도 ok 로 남는다: 서버 자체는
    살아 있고, 데이터 품질 문제와 프로세스 생존 문제를 한 필드에 섞지 않는다).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    import kis_auth
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
    return {
        "status": "ok",
        "ready": snapshot is not None,
        "snapshot": snapshot,
        "kis": kis_auth.token_status(),
    }


app.include_router(watchlist.router)
app.include_router(snapshot.router)
app.include_router(stocks.router)
app.include_router(indices.router)
app.include_router(market.router)
app.include_router(alerts.router)
app.include_router(paper.router)
app.include_router(stream.router)

# ★ 반드시 라우터 등록 **뒤**. `/` 마운트는 모든 경로에 걸리므로 먼저 걸면 API 를 가린다
#   (server/static.py 주석 참고). 빌드가 없으면 조용히 건너뛴다.
mount_web_ui(app, _BASE_DIR / "web" / "dist")
