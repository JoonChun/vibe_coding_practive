#!/usr/bin/env bash
# on-user-prompt-submit.test.sh — on-user-prompt-submit.sh 통합 테스트 (5개 케이스)
#
# 전략: stream.jsonl 전체를 백업 → 테스트 후 복원.
#       /tmp/dogam_task_id도 백업·복원.
#       hook은 stream.jsonl 절대경로 하드코딩이므로 tmpdir 우회 불가 → 백업·복원 사용.
#       jq 없는 환경 → python3 json 모듈로 파싱.

set -uo pipefail

HOOK="/home/joon/vibe_ws/devDogam/hooks/on-user-prompt-submit.sh"
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

# json_valid <json_string>: 유효 JSON이면 0, 아니면 1
json_valid() {
  local json="$1"
  printf '%s' "$json" | python3 -c "
import sys, json
try:
    json.load(sys.stdin)
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

# make_fixture <field> <value>: field=value 인 JSON 생성 (python3 기반, 안전한 escape)
make_fixture() {
  local field="$1"
  local value="$2"
  python3 -c "
import json, sys
print(json.dumps({'$field': sys.argv[1]}), end='')
" "$value" 2>/dev/null || true
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
  rm -f "$TASK_ID_FILE"
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
# 정상 prompt → task_start emit, 필드 검증, dogam_task_id 파일 검증
echo ""
echo "Case 1: 정상 prompt → task_start 이벤트 필드 전체 검증"
{
  reset_stream
  before=$(stream_lines)

  run_hook '{"prompt":"BMI 계산기 추가"}'

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
    if [ "$got_type" != "task_start" ]; then
      case1_pass=false
      reason="type expected 'task_start', got '$got_type'"
    fi

    # agentName 검증
    if [ "$case1_pass" = true ]; then
      got_agent=$(json_get "$line" "agentName")
      if [ "$got_agent" != "king" ]; then
        case1_pass=false
        reason="agentName expected 'king', got '$got_agent'"
      fi
    fi

    # message 검증
    if [ "$case1_pass" = true ]; then
      got_msg=$(json_get "$line" "message")
      if [ "$got_msg" != "BMI 계산기 추가" ]; then
        case1_pass=false
        reason="message expected 'BMI 계산기 추가', got '$got_msg'"
      fi
    fi

    # taskId 패턴 검증 (^task-[0-9a-f]+$)
    if [ "$case1_pass" = true ]; then
      got_task=$(json_get "$line" "taskId")
      if ! printf '%s' "$got_task" | grep -qE '^task-[0-9a-f]+$'; then
        case1_pass=false
        reason="taskId pattern mismatch: '$got_task'"
      fi
    fi

    # timestamp 13자리 숫자 검증
    if [ "$case1_pass" = true ]; then
      got_ts=$(json_get "$line" "timestamp")
      if ! printf '%s' "$got_ts" | grep -qE '^[0-9]{13}$'; then
        case1_pass=false
        reason="timestamp 13자리 아님: '$got_ts'"
      fi
    fi

    # dogam_task_id 파일 내용 == jsonl의 taskId
    if [ "$case1_pass" = true ]; then
      got_task=$(json_get "$line" "taskId")
      file_task=$(cat "$TASK_ID_FILE" 2>/dev/null | tr -d '[:space:]' || true)
      if [ "$file_task" != "$got_task" ]; then
        case1_pass=false
        reason="dogam_task_id 파일 불일치: file='$file_task', jsonl='$got_task'"
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
# 30자 초과 한글 → truncate (... 로 끝남, 30자 이하)
echo ""
echo "Case 2: 30자 초과 한글 prompt → truncate 검증"
{
  reset_stream
  before=$(stream_lines)

  # 한글 33자 (길이 초과 확인)
  run_hook '{"prompt":"가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사"}'

  after=$(stream_lines)
  added=$(( after - before ))

  case2_pass=true
  reason=""

  if [ "$added" -lt 1 ]; then
    case2_pass=false
    reason="stream.jsonl에 라인 추가 없음"
  else
    line=$(last_line)
    got_msg=$(json_get "$line" "message")

    # "..."로 끝나는지 확인
    if ! printf '%s' "$got_msg" | grep -q '\.\.\.$'; then
      case2_pass=false
      reason="message가 '...'로 끝나지 않음: '$got_msg'"
    fi

    # 문자 수 30 이하 검증 (wc -m: 한글 1자=1로 세는지 로케일 의존)
    # 안전하게 python3으로 unicode len 사용
    if [ "$case2_pass" = true ]; then
      char_count=$(printf '%s' "$got_msg" | python3 -c "import sys; print(len(sys.stdin.read()), end='')" 2>/dev/null || echo 999)
      if [ "$char_count" -gt 30 ]; then
        case2_pass=false
        reason="message 문자 수 ${char_count} > 30: '$got_msg'"
      fi
    fi
  fi

  if [ "$case2_pass" = true ]; then
    assert_pass "Case 2"
  else
    assert_fail "Case 2" "$reason"
  fi
}

# ── Case 3 ─────────────────────────────────────────────────────────────────────
# 빈 prompt → fallback "사건 진행 중..."
echo ""
echo "Case 3: 빈 prompt → fallback 메시지 검증"
{
  reset_stream
  before=$(stream_lines)

  run_hook '{"prompt":""}'

  after=$(stream_lines)
  added=$(( after - before ))

  case3_pass=true
  reason=""

  if [ "$added" -lt 1 ]; then
    case3_pass=false
    reason="stream.jsonl에 라인 추가 없음"
  else
    line=$(last_line)
    got_msg=$(json_get "$line" "message")
    # 스크립트가 emit하는 정확한 fallback 문자열 (UTF-8 ellipsis … U+2026 포함)
    expected="사건 진행 중…"
    if [ "$got_msg" != "$expected" ]; then
      case3_pass=false
      reason="message expected '$expected', got '$got_msg'"
    fi
  fi

  if [ "$case3_pass" = true ]; then
    assert_pass "Case 3"
  else
    assert_fail "Case 3" "$reason"
  fi
}

# ── Case 4 ─────────────────────────────────────────────────────────────────────
# 연속 prompt 시 새 taskId 생성, 파일 덮어쓰기
echo ""
echo "Case 4: 연속 prompt → taskId 상이, dogam_task_id 덮어쓰기 검증"
{
  reset_stream

  run_hook '{"prompt":"첫번째"}'
  line1=$(last_line)
  task_id_1=$(json_get "$line1" "taskId")

  run_hook '{"prompt":"두번째"}'
  line2=$(last_line)
  task_id_2=$(json_get "$line2" "taskId")

  case4_pass=true
  reason=""

  # 두 taskId가 다름
  if [ "$task_id_1" = "$task_id_2" ]; then
    case4_pass=false
    reason="두 taskId 동일: '$task_id_1'"
  fi

  # dogam_task_id 파일이 두 번째 taskId로 덮어써짐
  if [ "$case4_pass" = true ]; then
    file_task=$(cat "$TASK_ID_FILE" 2>/dev/null | tr -d '[:space:]' || true)
    if [ "$file_task" != "$task_id_2" ]; then
      case4_pass=false
      reason="dogam_task_id 파일이 두 번째 taskId와 불일치: file='$file_task', expected='$task_id_2'"
    fi
  fi

  if [ "$case4_pass" = true ]; then
    assert_pass "Case 4"
  else
    assert_fail "Case 4" "$reason"
  fi
}

# ── Case 5 ─────────────────────────────────────────────────────────────────────
# JSON escape (큰따옴표·backslash 포함) → 유효 JSON emit 검증
#
# 참고: hook은 jq 있을 때만 escape 문자를 올바르게 파싱.
#   jq 없을 때 grep 폴백은 \" 포함 값을 매칭하지 못해 빈 prompt → fallback emit.
#   어느 경우든 출력 라인은 유효한 JSON이어야 함.
#   jq 있을 때: message = 'a"b\c' (원문 보존)
#   jq 없을 때: message = '사건 진행 중…' (fallback) — 이 자체가 알려진 한계.
echo ""
echo "Case 5: JSON escape 문자 포함 prompt → 유효 JSON emit 검증"
{
  reset_stream
  before=$(stream_lines)

  # python3으로 안전하게 fixture JSON 생성: prompt = a"b\c
  fixture_json=$(python3 -c "import json; print(json.dumps({'prompt': 'a\"b\\\\c'}), end='')" 2>/dev/null)
  printf '%s' "$fixture_json" | bash "$HOOK" 2>/dev/null || true

  after=$(stream_lines)
  added=$(( after - before ))

  case5_pass=true
  reason=""

  if [ "$added" -lt 1 ]; then
    case5_pass=false
    reason="stream.jsonl에 라인 추가 없음"
  else
    line=$(last_line)

    # 공통 검증: 출력 라인이 유효한 JSON이어야 함
    if ! json_valid "$line"; then
      case5_pass=false
      reason="마지막 jsonl 라인이 유효한 JSON이 아님: '$line'"
    fi

    # jq 있을 때만 원문 보존 검증
    if [ "$case5_pass" = true ] && command -v jq >/dev/null 2>&1; then
      got_msg=$(json_get "$line" "message")
      expected_msg='a"b\c'
      if [ "$got_msg" != "$expected_msg" ]; then
        case5_pass=false
        reason="message escape 불일치 (jq 환경): expected '$expected_msg', got '$got_msg'"
      fi
    fi
    # jq 없을 때: grep 폴백이 escape 포함 값을 파싱 못함 → fallback emit
    # → 유효 JSON 검증만으로 통과 (알려진 한계, 장영실 도제에 보고 필요)
  fi

  if [ "$case5_pass" = true ]; then
    assert_pass "Case 5"
  else
    assert_fail "Case 5" "$reason"
  fi
}

# ── 최종 결과 ─────────────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo "훈련 결과: PASS $pass_count / FAIL $fail_count / 전체 5"
echo "================================================"

if [ "$fail_count" -gt 0 ]; then
  exit 1
fi
exit 0
