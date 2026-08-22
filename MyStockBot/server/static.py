"""빌드된 웹 UI(web/dist)를 API 서버가 함께 서빙한다.

## 왜 필요한가
`docker compose up` 을 하면 **API 만 뜨고 화면이 없었다.** Dockerfile 이 web 을 빌드하지
않았고 서버도 정적 파일을 서빙하지 않았기 때문이다. 개발 중에는 `npm run dev`(Vite dev
서버가 /api 를 프록시)로 쓰지만, 배포/체험 경로에서는 프로세스 하나로 화면까지 나와야 한다.

## 두 가지 함정
1. **SPA 클라이언트 라우팅.** `/paper` 를 새로고침하면 그 경로의 파일이 없으니 StaticFiles
   는 404 를 낸다. index.html 로 되돌려줘야 React Router 가 처리한다.
2. **`/api` 404 를 HTML 로 덮으면 안 된다.** 마운트를 `/` 에 걸면 라우터에 없는 `/api/...`
   경로까지 SPA 폴백에 걸려 index.html(HTML 200)이 나간다. 그러면 "그 엔드포인트가 아직
   없다"는 신호가 사라진다 — 실제로 이 저장소에서 사용자가 옛 커밋으로 서버를 띄웠을 때
   `{"detail":"Not Found"}` 라는 404 하나로 원인을 짚었다. 그 진단 능력을 없애면 안 된다.
   그래서 `api/` 로 시작하는 경로는 폴백하지 않고 404 를 그대로 통과시킨다.

인증은 손댈 필요가 없다 — `server/auth.py` 가 `/api` 로 시작하지 않는 경로를 이미
면제하므로 정적 파일은 토큰 없이 나가고, 화면이 뜬 뒤 API 호출에서 401 을 받아 토큰
입력 배너가 뜬다(의도된 흐름).
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

_API_PREFIX = "api/"          # StaticFiles 가 넘겨주는 path 는 선행 슬래시가 없다
_INDEX = "index.html"


class SPAStaticFiles(StaticFiles):
    """없는 경로는 index.html 로 되돌려주는 StaticFiles(단, /api 는 예외)."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            # API 경로의 404 는 404 로 남긴다(모듈 주석 2번 참고).
            if path.startswith(_API_PREFIX) or path == _API_PREFIX.rstrip("/"):
                raise
            return await super().get_response(_INDEX, scope)


def mount_web_ui(app: FastAPI, dist_dir: Path) -> bool:
    """web/dist 가 있으면 `/` 에 마운트한다. 마운트했으면 True.

    **반드시 include_router 들보다 뒤에 호출한다** — Starlette 는 등록 순서로 매칭하고
    `/` 마운트는 모든 경로에 걸리므로, 먼저 걸면 API 라우트를 전부 가려 버린다.

    빌드가 없으면(개발 중 `npm run dev` 사용) 조용히 건너뛴다 — 서버가 뜨지 못하게 만들
    이유가 없다.
    """
    index = dist_dir / _INDEX
    if not index.is_file():
        logger.info(
            "[web] 빌드 산출물이 없어 UI 서빙을 건너뜁니다(%s). "
            "개발 중이면 `cd web && npm run dev` 를 쓰세요.",
            dist_dir,
        )
        return False

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="web")
    logger.info("[web] UI 서빙 시작 — %s", dist_dir)
    return True
