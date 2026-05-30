#!/usr/bin/env bash
# on-subagent-pretty.sh — Reels용 페르소나 풀스타일 출력 훅
# 사용법: on-subagent-pretty.sh start | stop
# DOGAM_REELS_LOG env가 세팅된 경우에만 동작 (없으면 silent exit)

[ -z "$DOGAM_REELS_LOG" ] && exit 0

event_kind="${1:-start}"

stdin_json=$(cat)

# subagent_type 우선 → agent_type → tool_name 폴백
agent=""
if command -v jq >/dev/null 2>&1; then
  agent=$(echo "$stdin_json" | jq -r '
    .tool_input.subagent_type
    // .subagent_type
    // .agent_type
    // .agentName
    // .agent_name
    // empty
  ' 2>/dev/null)
fi
if [ -z "$agent" ]; then
  agent=$(echo "$stdin_json" | grep -oE '"subagent_type":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
if [ -z "$agent" ]; then
  agent=$(echo "$stdin_json" | grep -oE '"agent_type":"[^"]+"' | head -1 | cut -d'"' -f4)
fi
[ -z "$agent" ] && agent="unknown"

# description (tool_input.description) 추출 — 작업 한 줄 설명
desc=""
if command -v jq >/dev/null 2>&1; then
  desc=$(echo "$stdin_json" | jq -r '.tool_input.description // empty' 2>/dev/null)
fi
if [ -z "$desc" ]; then
  desc=$(echo "$stdin_json" | grep -oE '"description":"[^"]+"' | head -1 | cut -d'"' -f4)
fi

# 페르소나 풀네임 매핑 (16 에이전트)
case "$agent" in
  planner-dojeon)         persona="📐 정도전 (鄭道傳)" ;;
  implementer-yeongsil)   persona="🔧 장영실 (蔣英實)" ;;
  reviewer-sunsin)        persona="⚓ 이순신 (李舜臣)" ;;
  ideator-yagyong)        persona="💡 정약용 (丁若鏞)" ;;
  planning-hojo)          persona="📋 호조낭청 (戶曹郞廳)" ;;
  uiux-hwawon)            persona="📜 도화서 화원 (圖畵署 畵員)" ;;
  docs-sagwan)            persona="🖋️  사관 (史官)" ;;
  frontend-dancheong)     persona="🎨 단청도제 (丹靑徒弟)" ;;
  backend-gigwan)         persona="⚙️  기관도제 (機關徒弟)" ;;
  infra-tomok)            persona="🏗️  토목도제 (土木徒弟)" ;;
  integration-tongsin)    persona="📡 통신도제 (通信徒弟)" ;;
  security-chukhu)        persona="🔍 척후 (斥候)" ;;
  perf-uiwon)             persona="💊 의원 (醫員)" ;;
  test-gungwan)           persona="🧪 군관 (軍官)" ;;
  research-jeja)          persona="🎓 제자 (弟子)" ;;
  visual-hwagong)         persona="🎨 화공 (畵工)" ;;
  *)                      persona="🌀 $agent" ;;
esac

hms=$(date '+%H:%M:%S')

{
  if [ "$event_kind" = "stop" ] || [ "$event_kind" = "end" ]; then
    echo "[$hms] $persona — 회진"
    echo ""
  else
    echo "[$hms] $persona — 출진"
    [ -n "$desc" ] && echo "  └ 작업: $desc"
  fi
} >> "$DOGAM_REELS_LOG" 2>/dev/null || true

exit 0
