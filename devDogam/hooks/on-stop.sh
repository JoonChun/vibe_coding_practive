#!/usr/bin/env bash
# on-stop.sh — Claude Code Stop 훅
# devDogam 이벤트 스트림에 task_end 이벤트 기록
# 실패 시 silent fail (|| true로 처리됨)

# stdin에서 JSON 입력 받기 (Stop 훅은 주로 비어있음)
stdin_json=$(cat)

# taskId 세션 공유 (TMPDIR 기반, start와 동일하게 읽기)
task_id_file="${TMPDIR:-/tmp}/dogam_task_id"
task_id=$(cat "$task_id_file" 2>/dev/null || echo "task-fallback")

# 이벤트 ID 생성 (UUID)
event_id=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "uuid-fallback-$(date +%s%N)")

# timestamp (Unix ms, 정확히 13자리)
ts=$(date +%s%3N 2>/dev/null)
if [ -z "$ts" ] || [ "${#ts}" -ne 13 ]; then
  ts="$(date +%s)000"
fi

# === JSON 작성 ===
# jq 있으면 jq로 처리 (가장 안전)
jsonl_line=""
if command -v jq >/dev/null 2>&1; then
  jsonl_line=$(jq -c -n \
    --arg id "$event_id" \
    --argjson ts "$ts" \
    --arg type "task_end" \
    --arg agent "king" \
    --arg task "$task_id" \
    '{id:$id,timestamp:$ts,type:$type,agentName:$agent,taskId:$task}' 2>/dev/null)
fi

# jq 없거나 실패 시 sed escape 폴백
if [ -z "$jsonl_line" ]; then
  # backslash → \\, double quote → \", control chars → space
  esc_id=$(printf '%s' "$event_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
  esc_task=$(printf '%s' "$task_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
  jsonl_line="{\"id\":\"$esc_id\",\"timestamp\":$ts,\"type\":\"task_end\",\"agentName\":\"king\",\"taskId\":\"$esc_task\"}"
fi

# events/stream.jsonl에 append (절대경로 사용)
echo "$jsonl_line" >> "/home/joon/vibe_ws/devDogam/events/stream.jsonl" 2>/dev/null || true

exit 0
