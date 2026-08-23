# MyStockBot — API + 웹 UI 를 한 이미지에 담는다.
#
# 이전 버전은 API 만 담았다. 그래서 `docker compose up` 을 하면 서버는 뜨는데 **화면이
# 없었다** — web 을 빌드하지도, 서빙하지도 않았기 때문이다(.dockerignore 가 web/ 을
# 통째로 제외했다: "handled by Vercel"). Vercel 배포도 유효한 경로지만, 로컬에서 한 번에
# 띄워 보려는 사람에게는 쓸 수 없는 이미지였다.

# ────────────────────────────────────────────
# 1단계: 웹 UI 빌드 (산출물만 다음 단계로 넘긴다 — node·node_modules 는 안 남는다)
# ────────────────────────────────────────────
FROM node:20-slim AS web-build
WORKDIR /web

# 락파일 기준으로 설치한다(npm ci). package.json 만 먼저 복사해 레이어 캐시를 살린다.
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
# VITE_API_BASE 를 비워 둔다 — 같은 오리진의 서버가 /api 를 서빙하므로 상대경로가 맞다.
RUN npm run build

# ────────────────────────────────────────────
# 2단계: 런타임
# ────────────────────────────────────────────
FROM python:3.11-slim

# APScheduler·zoneinfo 가 Asia/Seoul 을 해석할 수 있어야 한다(slim 에는 tzdata 가 없다).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Seoul \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ★ 느슨한 requirements.txt 가 아니라 **고정된 락파일**로 설치한다.
#   requirements.txt 는 하한만 있어서 같은 커밋을 다시 빌드해도 상위 버전이 딸려 들어와
#   어제 되던 이미지가 오늘 깨질 수 있다. 락파일은 테스트가 통과한 버전 집합이다.
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY . .
COPY --from=web-build /web/dist ./web/dist

# ★ non-root 로 실행한다. 컨테이너가 쓰기하는 경로는 /app/data 하나뿐이다
#   (SQLite DB + KIS 토큰 캐시 — 둘 다 dirname(DB_PATH) 아래에 있다).
#   나머지 코드는 읽기만 하므로 root 소유로 남겨 둔다(앱이 자기 코드를 못 고친다).
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
 && mkdir -p /app/data \
 && chown -R app:app /app/data
USER app

EXPOSE 8000

# 헬스체크를 이미지에 넣어 둔다 — compose 없이 `docker run` 만 해도 상태가 보인다.
# slim 에는 curl 이 없어 파이썬 표준 라이브러리를 쓴다. /api/health 는 인증 예외 경로다.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"]

# 워커는 1개여야 한다 — APScheduler 와 KIS 실시간 WS 가 프로세스 내 단일 인스턴스를 전제한다.
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
