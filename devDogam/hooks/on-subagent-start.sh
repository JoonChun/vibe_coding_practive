#!/usr/bin/env bash
# on-subagent-start.sh — Claude Code 서브에이전트 시작 훅
# devDogam 이벤트 스트림에 agent_start 이벤트 기록
# 실패 시 silent fail (|| true로 처리됨)

# stdin에서 JSON 입력 받기
stdin_json=$(cat)

# agentName 추출 (다중 폴백: agent_type → agent_name → agentName → tool_name)
agent_name=$(echo "$stdin_json" | grep -oE '"agent_type":"[^"]+"' | head -1 | cut -d'"' -f4)
if [ -z "$agent_name" ]; then
  agent_name=$(echo "$stdin_json" | grep -oE '"agent_name":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$agent_name" ]; then
  agent_name=$(echo "$stdin_json" | grep -oE '"agentName":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$agent_name" ]; then
  agent_name=$(echo "$stdin_json" | grep -oE '"tool_name":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$agent_name" ]; then
  agent_name="unknown"
fi

# 이벤트 ID 생성 (UUID)
event_id=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "uuid-fallback-$(date +%s%N)")

# timestamp (Unix ms, 정확히 13자리)
ts=$(date +%s%3N 2>/dev/null)
if [ -z "$ts" ] || [ "${#ts}" -ne 13 ]; then
  ts="$(date +%s)000"
fi

# taskId 세션 공유 (TMPDIR 기반)
task_id_file="${TMPDIR:-/tmp}/dogam_task_id"
if [ ! -f "$task_id_file" ]; then
  short_uuid=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-' | head -c 8 || echo "$(date +%s)")
  echo "task-$short_uuid" > "$task_id_file" 2>/dev/null || true
fi
task_id=$(cat "$task_id_file" 2>/dev/null || echo "task-fallback")

# JSON escape 처리 — 변수들을 JSON-safe하게
# jq 있으면 jq로 처리 (가장 안전)
jsonl_line=""
if command -v jq >/dev/null 2>&1; then
  jsonl_line=$(jq -c -n \
    --arg id "$event_id" \
    --argjson ts "$ts" \
    --arg type "agent_start" \
    --arg agent "$agent_name" \
    --arg task "$task_id" \
    '{id:$id,timestamp:$ts,type:$type,agentName:$agent,taskId:$task}' 2>/dev/null)
fi

# jq 없거나 실패 시 sed escape 폴백
if [ -z "$jsonl_line" ]; then
  # backslash → \\, double quote → \", control chars → space
  esc_agent=$(printf '%s' "$agent_name" | sed 's/\\/\\\\/g; s/"/\\"/g; s/[[:cntrl:]]/ /g')
  esc_id=$(printf '%s' "$event_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
  esc_task=$(printf '%s' "$task_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
  jsonl_line="{\"id\":\"$esc_id\",\"timestamp\":$ts,\"type\":\"agent_start\",\"agentName\":\"$esc_agent\",\"taskId\":\"$esc_task\"}"
fi

# events/stream.jsonl에 append (절대경로 사용)
echo "$jsonl_line" >> "/home/joon/vibe_ws/devDogam/events/stream.jsonl" 2>/dev/null || true

# (선택) 에러 로그 기록
if [ $? -ne 0 ]; then
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Failed to append event for agent: $agent_name" >> "/home/joon/vibe_ws/devDogam/events/hook-errors.log" 2>/dev/null || true
fi

exit 0
