#!/usr/bin/env bash
# MyStockBot 로컬 실행 — 실패하면 그 이유와 조치를 말해준다.
#
# ## 왜 스크립트인가
# README 에 두 줄짜리 명령(`cd web && npm run build` / `uvicorn server.main:app`)을 적었더니
# 사용자 환경에서 에러가 났다. 원인은 문서가 **말 없이 가정한** 두 가지였다:
#   · `uvicorn` 이 PATH 에 있다      → 없으면 `command not found`
#   · 8000 포트가 비어 있다          → 이미 서버가 돌면 `Address already in use`
# 둘 다 실행 전에 알 수 있는 것이므로, 확인해서 사람이 읽을 수 있는 말로 알려준다.
# 출력 문구는 tests/test_run_local_script.py 가 잠그고 있다 — 이 스크립트의 산출물이다.
#
# ## 사용
#   ./scripts/run_local.sh              # 8000 포트
#   PORT=8080 ./scripts/run_local.sh    # 다른 포트
#   MYSTOCKBOT_RUN_LOCAL_DRY=1 ...      # 실제로 띄우지 않고 점검·명령만 출력
set -euo pipefail

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

# ── 실행 위치 ──
# server/main.py 의 sys.path 설정이 MyStockBot/ 실행을 전제한다.
if [ ! -f "server/main.py" ] || [ ! -f "config.py" ]; then
  echo "✗ 실행 위치가 잘못됐습니다." >&2
  echo "  MyStockBot/ 디렉터리에서 실행해야 합니다(server/main.py 가 그 위치를 전제)." >&2
  echo "  예: cd ~/vibe_ws/MyStockBot && ./scripts/run_local.sh" >&2
  exit 2
fi

# ── 파이썬 ──
# `uvicorn` 실행파일을 찾지 않는다. PATH 에 없을 수 있고(실제로 그래서 막혔다),
# `python -m uvicorn` 은 그 파이썬에 설치돼 있으면 항상 동작한다.
PY=""
for candidate in "${PYTHON:-}" python3 python /usr/bin/python3 /usr/local/bin/python3; do
  [ -n "$candidate" ] || continue
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
  if [ -x "$candidate" ]; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "✗ 파이썬을 찾지 못했습니다. PYTHON=/path/to/python 으로 지정하세요." >&2
  exit 2
fi

# ── 포트 ──
# uvicorn 의 트레이스백보다 먼저, 읽을 수 있는 말로 알려준다.
if "$PY" - "$HOST" "$PORT" <<'EOF'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket()
try:
    s.connect((host, port))          # 연결되면 = 누가 듣고 있다
    sys.exit(0)
except OSError:
    sys.exit(1)
finally:
    s.close()
EOF
then
  echo "✗ ${HOST}:${PORT} 포트가 이미 사용 중입니다." >&2
  echo "  이미 띄워둔 서버가 있는 것 같습니다. 둘 중 하나를 하세요:" >&2
  echo "    · 기존 서버를 끄기" >&2
  echo "    · 다른 포트로 띄우기 —  PORT=8080 ./scripts/run_local.sh" >&2
  exit 3
fi

# ── 웹 빌드 ──
# 없어도 치명적이지 않다. API 는 뜨고, 화면은 `npm run dev` 로 따로 띄우면 된다.
DIST="${MYSTOCKBOT_WEB_DIST:-web/dist}"
if [ -f "${DIST}/index.html" ]; then
  echo "✓ 웹 UI 빌드 있음 — 서버가 화면까지 서빙합니다."
else
  echo "ⓘ 웹 UI 빌드가 없어 API 만 뜹니다. 화면까지 한 프로세스로 띄우려면:"
  echo "    (cd web && npm install && npm run build)  후 다시 실행"
  echo "  개발 중이라면 별도 터미널에서:  cd web && npm run dev"
fi

echo "→ http://localhost:${PORT}"
echo "  실행 명령: $PY -m uvicorn server.main:app --host $HOST --port $PORT"

if [ -n "${MYSTOCKBOT_RUN_LOCAL_DRY:-}" ]; then
  echo "(DRY 모드 — 실제로 띄우지 않았습니다)"
  exit 0
fi

exec "$PY" -m uvicorn server.main:app --host "$HOST" --port "$PORT" "$@"
