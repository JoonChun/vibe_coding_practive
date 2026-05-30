#!/usr/bin/env bash
# start-reels-session.sh — tmux 분할판 + 페르소나 로그 viewer + claude 실행
# 사용법:
#   ./start-reels-session.sh                  # 그냥 claude
#   ./start-reels-session.sh --dangerously-skip-permissions
#   ./start-reels-session.sh -- (claude에 전달할 인자들)
#
# 좌 pane: claude (메인 작업)
# 우 pane: 페르소나 풀스타일 출진 기록부 (tail -F)
set -e

SESSION_TS=$(date +%Y%m%d-%H%M%S)
LOG_DIR="/home/joon/vibe_ws/.claude/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/session-$SESSION_TS.log"

# 헤더 작성
cat > "$LOG_FILE" <<EOF
════════════════════════════════════════════════════════
  📜 조선왕조 개발실록 — 출진 기록부
════════════════════════════════════════════════════════
  세션:  $SESSION_TS
  시작:  $(date '+%Y-%m-%d %H:%M:%S')
  로그:  $LOG_FILE
════════════════════════════════════════════════════════

(메인 pane에서 작업이 시작되면 이곳에 도제들의 출진 기록이 떨어집니다)

EOF

export DOGAM_REELS_LOG="$LOG_FILE"

if ! command -v tmux >/dev/null 2>&1; then
  echo "[!] tmux 없음. claude 직접 실행. 별도 터미널에서:"
  echo "    tail -F '$LOG_FILE'"
  echo ""
  exec claude "$@"
fi

SESSION_NAME="dogam-$SESSION_TS"

# 우 pane viewer: less +F (follow + scrollback)가 reels에 더 자연스러움
VIEWER_CMD="less +F -R '$LOG_FILE'"
# tail 선호 시 아래로 교체
# VIEWER_CMD="tail -F -n +1 '$LOG_FILE'"

if [ -n "$TMUX" ]; then
  # 이미 tmux 안 — split-window만
  tmux split-window -h -p 38 "$VIEWER_CMD"
  tmux select-pane -L
  exec claude "$@"
else
  # 새 tmux 세션
  CLAUDE_ARGS="$*"
  tmux new-session -d -s "$SESSION_NAME" \
    -e "DOGAM_REELS_LOG=$LOG_FILE" \
    "claude $CLAUDE_ARGS"
  tmux split-window -h -p 38 -t "$SESSION_NAME" "$VIEWER_CMD"
  tmux select-pane -t "$SESSION_NAME" -L
  tmux set-option -t "$SESSION_NAME" status-right \
    " 📜 reels session #S | $(date '+%Y-%m-%d') "
  exec tmux attach -t "$SESSION_NAME"
fi
