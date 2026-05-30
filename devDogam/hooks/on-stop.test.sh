#!/usr/bin/env bash
# on-stop.test.sh — on-stop.sh 통합 테스트 (3개 케이스)
#
# 전략: stream.jsonl 전체를 백업 → 테스트 후 복원.
#       /tmp/dogam_task_id도 백업·복원.
#       hook은 stream.jsonl 절대경로 하드코딩이므로 tmpdir 우회 불가 → 백업·복원 사용.
#       jq 없는 환경 → python3 json 모듈로 파싱.

set -uo pipefail

HOOK="/home/joon/vibe_ws/devDogam/hooks/on-stop.sh"
STREAM="/home/joon/vibe_ws/devDogam/events/stream.jsonl"
TASK_ID_FILE="/tmp/dogam_task_id"

pass_count=0
fail_count=0

# ── 전역 백업 ──────────────────────────────────────────────────────────────────
STREAM_BACKUP=$(mktemp)
TASK_ID_BACKUP=$(mktemp)

cp "$STREAM" "$STREAM_BACKUP" 2>/dev/null || true
if [ -f "$TASK_ID_FILE" ]; then
  cp "$TASK_ID_FILE" "$TASK_ID_BACKUP" 2>/dev/null || true
fi

# EXIT 시 원복
cleanup_all() {
  cp "$STREAM_BACKUP" "$STREAM" 2>/dev/null || true
  if [ -s "$TASK_ID_BACKUP" ]; then
    cp "$TASK_ID_BACKUP" "$TASK_ID_FILE" 2>/dev/null || true
  else
    rm -f "$TASK_ID_FILE"
  fi
  rm -f "$STREAM_BACKUP" "$TASK_ID_BACKUP"
}
trap cleanup_all EXIT

# ── JSON 파싱 헬퍼 (python3 기반, jq 대체) ───────────────────────────────────
# json_get <json_string> <field>
# 지정 필드 값을 문자열로 출력 (문자열·숫자 모두)
json_get() {
  local json="$1"
  local field="$2"
  printf '%s' "$json" | python3 -c "
import sys, json
try:
    obj = json.load(sys.stdin)
    val = obj.get('$field', '')
    print(val, end='')
except Exception:
    pass
" 2>/dev/null || true
}

# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

# stream.jsonl 현재 라인 수 반환
stream_lines() {
  wc -l < "$STREAM" 2>/dev/null || echo 0
}

# stream.jsonl 마지막 라인 반환
last_line() {
  tail -n 1 "$STREAM" 2>/dev/null || true
}

# 케이스 시작 전 stream.jsonl을 백업 상태로 초기화 (테스트 격리)
reset_stream() {
  cp "$STREAM_BACKUP" "$STREAM" 2>/dev/null || true
}

# PASS/FAIL 카운터 및 출력
assert_pass() {
  local name="$1"
  echo "  PASS: $name"
  pass_count=$(( pass_count + 1 ))
}

assert_fail() {
  local name="$1"
  local reason="$2"
  echo "  FAIL: $name -- $reason"
  fail_count=$(( fail_count + 1 ))
}

# hook 실행 (stdin JSON 전달)
run_hook() {
  local stdin_json="$1"
  printf '%s' "$stdin_json" | bash "$HOOK" 2>/dev/null || true
}

# ── Case 1 ─────────────────────────────────────────────────────────────────────
# dogam_task_id 미리 기록 → task_end emit, 필드 검증
echo ""
echo "Case 1: dogam_task_id 사전 기록 → task_end 이벤트 필드 검증"
{
  reset_stream
  # 사전: task_id_file에 task-deadbeef 기록
  printf 'task-deadbeef' > "$TASK_ID_FILE"

  before=$(stream_lines)
  run_hook '{}'
  after=$(stream_lines)
  added=$(( after - before ))

  case1_pass=true
  reason=""

  if [ "$added" -lt 1 ]; then
    case1_pass=false
    reason="stream.jsonl에 라인 추가 없음"
  else
    line=$(last_line)

    # type 검증
    got_type=$(json_get "$line" "type")
    if [ "$got_type" != "task_end" ]; then
      case1_pass=false
      reason="type expected 'task_end', got '$got_type'"
    fi

    # agentName 검증
    if [ "$case1_pass" = true ]; then
      got_agent=$(json_get "$line" "agentName")
      if [ "$got_agent" != "king" ]; then
        case1_pass=false
        reason="agentName expected 'king', got '$got_agent'"
      fi
    fi

    # taskId 검증
    if [ "$case1_pass" = true ]; then
      got_task=$(json_get "$line" "taskId")
      if [ "$got_task" != "task-deadbeef" ]; then
        case1_pass=false
        reason="taskId expected 'task-deadbeef', got '$got_task'"
      fi
    fi
  fi

  if [ "$case1_pass" = true ]; then
    assert_pass "Case 1"
  else
    assert_fail "Case 1" "$reason"
  fi
}

# ── Case 2 ─────────────────────────────────────────────────────────────────────
# dogam_task_id 없음 → fallback taskId 검증
echo ""
echo "Case 2: dogam_task_id 없을 때 fallback taskId 검증"
{
  reset_stream
  # 사전: task_id_file 없음
  rm -f "$TASK_ID_FILE"

  # on-stop.sh line 11: task_id=$(cat "$task_id_file" 2>/dev/null || echo "task-fallback")
  expected_fallback="task-fallback"

  before=$(stream_lines)
  run_hook '{}'
  after=$(stream_lines)
  added=$(( after - before ))

  case2_pass=true
  reason=""

  if [ "$added" -lt 1 ]; then
    case2_pass=false
    reason="stream.jsonl에 라인 추가 없음"
  else
    line=$(last_line)
    got_task=$(json_get "$line" "taskId")
    if [ "$got_task" != "$expected_fallback" ]; then
      case2_pass=false
      reason="taskId expected '$expected_fallback', got '$got_task'"
    fi
  fi

  if [ "$case2_pass" = true ]; then
    assert_pass "Case 2"
  else
    assert_fail "Case 2" "$reason"
  fi
}

# ── Case 3 ─────────────────────────────────────────────────────────────────────
# stream.jsonl append-only 검증: 기존 라인 수 N → 실행 후 N+1, 기존 라인 불변
echo ""
echo "Case 3: stream.jsonl append-only 검증 (기존 라인 불변, N+1 라인)"
{
  reset_stream
  printf 'task-abc123' > "$TASK_ID_FILE"

  # 기존 라인 전체 캡처
  before=$(stream_lines)
  existing_content=$(cat "$STREAM" 2>/dev/null || true)

  run_hook '{}'

  after=$(stream_lines)
  added=$(( after - before ))

  case3_pass=true
  reason=""

  # 정확히 1줄 추가됐는지
  if [ "$added" -ne 1 ]; then
    case3_pass=false
    reason="추가 라인 수 expected 1, got $added"
  fi

  # 기존 라인 불변 검증: 앞 N줄이 before 내용과 동일한지
  if [ "$case3_pass" = true ] && [ "$before" -gt 0 ]; then
    preserved=$(head -n "$before" "$STREAM" 2>/dev/null || true)
    if [ "$preserved" != "$existing_content" ]; then
      case3_pass=false
      reason="기존 라인 변경 감지 (append-only 위반)"
    fi
  fi

  if [ "$case3_pass" = true ]; then
    assert_pass "Case 3"
  else
    assert_fail "Case 3" "$reason"
  fi
}

# ── 최종 결과 ─────────────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "훈련 결과: PASS $pass_count / FAIL $fail_count / 전체 3"
echo "================================================"

if [ "$fail_count" -gt 0 ]; then
  exit 1
fi
exit 0
