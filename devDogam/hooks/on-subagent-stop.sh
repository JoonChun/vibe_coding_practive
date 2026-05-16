#!/usr/bin/env bash
# on-subagent-stop.sh — Claude Code 서브에이전트 종료 훅
# devDogam 이벤트 스트림에 agent_end 이벤트 기록
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

# taskId 세션 공유 (TMPDIR 기반, start와 동일하게 읽기)
task_id_file="${TMPDIR:-/tmp}/dogam_task_id"
if [ ! -f "$task_id_file" ]; then
  short_uuid=$(cat /proc/sys/kernel/random/uuid 2>/dev/null | tr -d '-' | head -c 8 || echo "$(date +%s)")
  echo "task-$short_uuid" > "$task_id_file" 2>/dev/null || true
fi
task_id=$(cat "$task_id_file" 2>/dev/null || echo "task-fallback")

# === agent_message 요약 추출 ===
# transcript_path 추출 시도
transcript_path=$(echo "$stdin_json" | grep -oE '"transcript_path":"[^"]+"' | head -1 | cut -d'"' -f4)

# realpath 정규화 — symlink resolve, path traversal 제거. path traversal 공격 방어.
if [ -n "$transcript_path" ]; then
  if command -v realpath >/dev/null 2>&1; then
    transcript_path=$(realpath -e "$transcript_path" 2>/dev/null || echo "")
  elif command -v readlink >/dev/null 2>&1; then
    transcript_path=$(readlink -f "$transcript_path" 2>/dev/null || echo "")
    [ -f "$transcript_path" ] || transcript_path=""
  fi
fi

# transcript에서 마지막 assistant message의 첫 H2 헤딩 추출
summary=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
  # 마지막 assistant message line 찾기 (대형 transcript OOM 방어: 마지막 200 라인만)
  last_assistant_line=$(tail -n 200 "$transcript_path" 2>/dev/null | tac 2>/dev/null | grep -m1 '"type":"assistant"' || echo "")

  if [ -n "$last_assistant_line" ]; then
    # JSON에서 "text":"..." 필드 추출
    # escaped newline \n을 실제 newline으로 변환하여 parsing
    last_assistant_text=$(printf '%s' "$last_assistant_line" | \
      sed 's/\\"/\x00/g' | \
      grep -oE '"text":"[^"]+"' | head -1 | cut -d'"' -f4 | \
      sed 's/\\n/\n/g' || echo "")

    if [ -n "$last_assistant_text" ]; then
      # 첫 H2 헤딩 찾기 (^## 로 시작)
      h2_line=$(printf '%s' "$last_assistant_text" | grep -E '^##' | head -1 || echo "")

      if [ -n "$h2_line" ]; then
        # 3단 fallback으로 페르소나 prefix 제거
        # 1차: "## <anything> — <content>" 또는 "## <anything> : <content>" 패턴
        cleaned=$(printf '%s' "$h2_line" | sed -E 's/^##\s+[^—:]+[—:]\s*(.+)$/\1/' 2>/dev/null || echo "")

        if [ -z "$cleaned" ] || [ "$cleaned" = "$h2_line" ]; then
          # 2차: ## 만 제거
          cleaned=$(printf '%s' "$h2_line" | sed 's/^##\s*//' || echo "")

          # 3차: 16 에이전트 페르소나명 제거 (선택적 "의" 포함)
          # sed -E alternation: (A|B|C|...|P) → 15개 페르소나 + "의" 선택적
          cleaned=$(printf '%s' "$cleaned" | sed -E \
            's/^(정도전|장영실|이순신|정약용|호조낭청|도화서 화원|사관|단청도제|기관도제|토목도제|통신도제|척후|의원|군관|제자|화공)의?\s+//' \
            2>/dev/null || echo "$cleaned")
        fi

        # markdown 및 control 문자 제거
        cleaned=$(printf '%s' "$cleaned" | sed 's/[*_`\[\]()]//g' | \
          tr -d '\r' | \
          sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || echo "")

        # 길이 제한: 30자 이내 (한글 1자 = 1자)
        if [ -n "$cleaned" ]; then
          char_count=${#cleaned}
          if [ "$char_count" -gt 30 ]; then
            # 27자 + "..."
            summary=$(printf '%s' "$cleaned" | head -c 27)
            summary="${summary}..."
          else
            summary="$cleaned"
          fi
        fi
      fi
    fi
  fi
fi

# === JSON escape 처리 ===
# agent_message 생성 (summary가 비어있지 않으면)
agent_msg_line=""
if [ -n "$summary" ]; then
  # timestamp: agent_end보다 1ms 이전 (순서 보장)
  msg_ts=$((ts - 1))

  if command -v jq >/dev/null 2>&1; then
    agent_msg_line=$(jq -c -n \
      --arg id "$event_id" \
      --argjson timestamp "$msg_ts" \
      --arg type "agent_message" \
      --arg agent "$agent_name" \
      --arg task "$task_id" \
      --arg message "$summary" \
      '{id:$id,timestamp:$timestamp,type:$type,agentName:$agent,taskId:$task,message:$message}' 2>/dev/null)
  fi

  # jq 없거나 실패 시 sed escape 폴백
  if [ -z "$agent_msg_line" ]; then
    esc_summary=$(printf '%s' "$summary" | sed 's/\\/\\\\/g; s/"/\\"/g; s/[[:cntrl:]]/ /g')
    esc_agent=$(printf '%s' "$agent_name" | sed 's/\\/\\\\/g; s/"/\\"/g; s/[[:cntrl:]]/ /g')
    esc_id=$(printf '%s' "$event_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
    esc_task=$(printf '%s' "$task_id" | sed 's/\\/\\\\/g; s/"/\\"/g')
    agent_msg_line="{\"id\":\"$esc_id\",\"timestamp\":$msg_ts,\"type\":\"agent_message\",\"agentName\":\"$esc_agent\",\"taskId\":\"$esc_task\",\"message\":\"$esc_summary\"}"
  fi

  # agent_message 먼저 append
  echo "$agent_msg_line" >> "/home/joon/vibe_ws/devDogam/events/stream.jsonl" 2>/dev/null || true
fi

# === agent_end 이벤트 ===
# jq 있으면 jq로 처리 (가장 안전)
jsonl_line=""
if command -v jq >/dev/null 2>&1; then
  jsonl_line=$(jq -c -n \
    --arg id "$event_id" \
    --argjson ts "$ts" \
    --arg type "agent_end" \
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
  jsonl_line="{\"id\":\"$esc_id\",\"timestamp\":$ts,\"type\":\"agent_end\",\"agentName\":\"$esc_agent\",\"taskId\":\"$esc_task\"}"
fi

# events/stream.jsonl에 append (절대경로 사용)
echo "$jsonl_line" >> "/home/joon/vibe_ws/devDogam/events/stream.jsonl" 2>/dev/null || true

# (선택) 에러 로그 기록
if [ $? -ne 0 ]; then
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] Failed to append event for agent: $agent_name" >> "/home/joon/vibe_ws/devDogam/events/hook-errors.log" 2>/dev/null || true
fi

exit 0
