#!/usr/bin/env bash
# on-user-prompt-submit.sh — Claude Code UserPromptSubmit 훅
# devDogam 이벤트 스트림에 task_start 이벤트 기록
# 실패 시 silent fail (|| true로 처리됨)

# stdin에서 JSON 입력 받기
stdin_json=$(cat)

# prompt 추출 (다중 폴백: prompt → content → message → empty)
prompt=$(echo "$stdin_json" | jq '.prompt // .content // .message // empty' 2>/dev/null | tr -d '"')
if [ -z "$prompt" ]; then
  # jq 실패 시 grep 폴백
  prompt=$(echo "$stdin_json" | grep -oE '"prompt":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$prompt" ]; then
  prompt=$(echo "$stdin_json" | grep -oE '"content":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$prompt" ]; then
  prompt=$(echo "$stdin_json" | grep -oE '"message":"[^"]+"' | head -1 | cut -d'"' -f4)
fi

# 빈 prompt 시 fallback
if [ -z "$prompt" ]; then
  prompt="사건 진행 중…"
fi

# markdown 및 control 문자 제거 (on-subagent-stop.sh line 90 패턴)
cleaned=$(printf '%s' "$prompt" | sed 's/[*_`\[\]()]//g' | \
  tr -d '\r' | \
  sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || echo "")

# 길이 제한: 30자 이내 (한글 1자 = 1자)
# 31자 이상이면 27자 + "..." (on-subagent-stop.sh line 94-103 패턴)
if [ -n "$cleaned" ]; then
  char_count=${#cleaned}
  if [ "$char_count" -gt 30 ]; then
    # 27자 + "..."
    summary=$(printf '%s' "$cleaned" | head -c 27)
    summary="${summary}..."
  else
    summary="$cleaned"
  fi
else
  summary="$cleaned"
fi

# 새 taskId 생성 및 TMPDIR에 저장
task_id_file="${TMPDIR:-/tmp}/dogam_task_id"
short_uuid=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-' | head -c 8 || echo "$(date +%s)")
task_id="task-$short_uuid"
echo "$task_id" > "$task_id_file" 2>/dev/null || true

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
    --arg type "task_start" \
    --arg agent "king" \
    --arg task "$task_id" \
    --arg msg "$summary" \
    '{id:$id,timestamp:$ts,type:$type,agentName:$agent,taskId:$task,message:$msg}' 2>/dev/null)
fi

# jq 없거나 실패 시 sed escape 폴백
if [ -z "$jsonl_line" ]; then
  # backslash → \\, double quote → \", control chars → space
  esc_summary=$(printf '%s' "$summary" | sed 's/\\/\\\\/g; s/"/\\"/g; s/[[:cntrl:]]/ /g')
  esc_id=$(printf '%s' "$event_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
  esc_task=$(printf '%s' "$task_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
  jsonl_line="{\"id\":\"$esc_id\",\"timestamp\":$ts,\"type\":\"task_start\",\"agentName\":\"king\",\"taskId\":\"$esc_task\",\"message\":\"$esc_summary\"}"
fi

# events/stream.jsonl에 append (절대경로 사용)
echo "$jsonl_line" >> "/home/joon/vibe_ws/devDogam/events/stream.jsonl" 2>/dev/null || true

exit 0
