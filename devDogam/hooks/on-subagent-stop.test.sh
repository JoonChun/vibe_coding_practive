#!/usr/bin/env bash
# on-subagent-stop.test.sh — on-subagent-stop.sh 통합 테스트 (5개 케이스)
#
# 전략 (옵션 B):
#   hook을 직접 실행 → stream.jsonl에 추가된 라인 검증 → 테스트 후 추가 라인 제거
#   프로덕션 stream.jsonl을 오염시키지 않도록 각 케이스마다 추가된 라인 수를 추적·제거.

set -euo pipefail

HOOK="/home/joon/vibe_ws/devDogam/hooks/on-subagent-stop.sh"
STREAM="/home/joon/vibe_ws/devDogam/events/stream.jsonl"

pass_count=0
fail_count=0

# ── 헬퍼 함수 ─────────────────────────────────────────────────────────────────

# stream.jsonl 현재 라인 수 반환
stream_lines() {
  wc -l < "$STREAM" 2>/dev/null || echo 0
}

# N줄 추가됐을 때 마지막 N줄 가져오기
last_n_lines() {
  local n="$1"
  tail -n "$n" "$STREAM" 2>/dev/null || true
}

# stream.jsonl에서 마지막 N줄 제거 (테스트 후 cleanup)
remove_last_n_lines() {
  local n="$1"
  if [ "$n" -le 0 ]; then
    return 0
  fi
  local total
  total=$(wc -l < "$STREAM" 2>/dev/null || echo 0)
  local keep=$(( total - n ))
  if [ "$keep" -lt 0 ]; then
    keep=0
  fi
  # tmpfile로 안전하게 덮어쓰기
  local tmp
  tmp=$(mktemp)
  head -n "$keep" "$STREAM" > "$tmp" 2>/dev/null || true
  mv "$tmp" "$STREAM"
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
  echo "  FAIL: $name — $reason"
  fail_count=$(( fail_count + 1 ))
}

# transcript JSONL 파일 생성 헬퍼
# 인자: h2_heading (H2 헤딩 텍스트, 빈 문자열이면 H2 없음)
make_transcript() {
  local h2="$1"
  local tmp
  tmp=$(mktemp --suffix=".jsonl")

  local text_content
  if [ -n "$h2" ]; then
    text_content="${h2}\\n본문 내용입니다."
  else
    text_content="본문만 있고 헤딩은 없습니다."
  fi

  # JSONL 한 줄: assistant type
  printf '{"type":"assistant","message":{"content":[{"type":"text","text":"%s"}]}}\n' \
    "$text_content" >> "$tmp"

  echo "$tmp"
}

# hook 호출 (stdin으로 JSON 전달)
run_hook() {
  local transcript_path="$1"
  local agent_name="${2:-planner-dojeon}"
  local stdin_json
  stdin_json=$(printf '{"agent_type":"%s","transcript_path":"%s"}' \
    "$agent_name" "$transcript_path")
  echo "$stdin_json" | bash "$HOOK" 2>/dev/null || true
}

# ── Case 1 ─────────────────────────────────────────────────────────────────────
# ## 정도전의 초안 — BMI 계산기 추가  →  "BMI 계산기 추가" 추출
echo ""
echo "Case 1: '## 정도전의 초안 — BMI 계산기 추가' → agent_message 'BMI 계산기 추가'"
{
  transcript=$(make_transcript "## 정도전의 초안 — BMI 계산기 추가")
  before=$(stream_lines)

  run_hook "$transcript" "planner-dojeon"

  after=$(stream_lines)
  added=$(( after - before ))

  cleanup_needed="$added"

  if [ "$added" -ge 1 ]; then
    new_lines=$(last_n_lines "$added")
    # agent_message 라인이 있는지 확인
    if echo "$new_lines" | grep -q '"type":"agent_message"'; then
      # message 값 추출
      extracted=$(echo "$new_lines" | grep '"type":"agent_message"' | \
        grep -oE '"message":"[^"]+"' | head -1 | cut -d'"' -f4 || true)
      if [ "$extracted" = "BMI 계산기 추가" ]; then
        assert_pass "Case 1"
      else
        assert_fail "Case 1" "expected 'BMI 계산기 추가', got '$extracted'"
      fi
    else
      assert_fail "Case 1" "agent_message 라인 없음 (추가된 라인: $added)"
    fi
  else
    assert_fail "Case 1" "stream.jsonl에 라인 추가 없음"
  fi

  remove_last_n_lines "$cleanup_needed"
  rm -f "$transcript"
}

# ── Case 2 ─────────────────────────────────────────────────────────────────────
# ## 장영실의 보고  →  "보고" 추출
echo ""
echo "Case 2: '## 장영실의 보고' → agent_message '보고'"
{
  transcript=$(make_transcript "## 장영실의 보고")
  before=$(stream_lines)

  run_hook "$transcript" "implementer-yeongsil"

  after=$(stream_lines)
  added=$(( after - before ))
  cleanup_needed="$added"

  if [ "$added" -ge 1 ]; then
    new_lines=$(last_n_lines "$added")
    if echo "$new_lines" | grep -q '"type":"agent_message"'; then
      extracted=$(echo "$new_lines" | grep '"type":"agent_message"' | \
        grep -oE '"message":"[^"]+"' | head -1 | cut -d'"' -f4 || true)
      if [ "$extracted" = "보고" ]; then
        assert_pass "Case 2"
      else
        assert_fail "Case 2" "expected '보고', got '$extracted'"
      fi
    else
      assert_fail "Case 2" "agent_message 라인 없음"
    fi
  else
    assert_fail "Case 2" "stream.jsonl에 라인 추가 없음"
  fi

  remove_last_n_lines "$cleanup_needed"
  rm -f "$transcript"
}

# ── Case 3 ─────────────────────────────────────────────────────────────────────
# ## 호조낭청 일정 안  →  "일정 안" 추출 (3차 fallback: 페르소나명 strip)
echo ""
echo "Case 3: '## 호조낭청 일정 안' → agent_message '일정 안'"
{
  transcript=$(make_transcript "## 호조낭청 일정 안")
  before=$(stream_lines)

  run_hook "$transcript" "planning-hojo"

  after=$(stream_lines)
  added=$(( after - before ))
  cleanup_needed="$added"

  if [ "$added" -ge 1 ]; then
    new_lines=$(last_n_lines "$added")
    if echo "$new_lines" | grep -q '"type":"agent_message"'; then
      extracted=$(echo "$new_lines" | grep '"type":"agent_message"' | \
        grep -oE '"message":"[^"]+"' | head -1 | cut -d'"' -f4 || true)
      if [ "$extracted" = "일정 안" ]; then
        assert_pass "Case 3"
      else
        assert_fail "Case 3" "expected '일정 안', got '$extracted'"
      fi
    else
      assert_fail "Case 3" "agent_message 라인 없음"
    fi
  else
    assert_fail "Case 3" "stream.jsonl에 라인 추가 없음"
  fi

  remove_last_n_lines "$cleanup_needed"
  rm -f "$transcript"
}

# ── Case 4 ─────────────────────────────────────────────────────────────────────
# H2 없는 transcript → agent_message 안 emit (agent_end만 추가)
echo ""
echo "Case 4: H2 없는 transcript → agent_message 미발행"
{
  transcript=$(make_transcript "")
  before=$(stream_lines)

  run_hook "$transcript" "planner-dojeon"

  after=$(stream_lines)
  added=$(( after - before ))
  cleanup_needed="$added"

  if [ "$added" -ge 1 ]; then
    new_lines=$(last_n_lines "$added")
    if echo "$new_lines" | grep -q '"type":"agent_message"'; then
      assert_fail "Case 4" "H2 없는데 agent_message가 emit됨"
    else
      # agent_end만 추가된 것이 정상
      assert_pass "Case 4"
    fi
  else
    # 라인 추가가 전혀 없어도 silent fail 범주 (hook 자체는 exit 0)
    assert_pass "Case 4"
  fi

  remove_last_n_lines "$cleanup_needed"
  rm -f "$transcript"
}

# ── Case 5 ─────────────────────────────────────────────────────────────────────
# transcript_path가 존재하지 않는 경로 → agent_message 안 emit (silent fail)
echo ""
echo "Case 5: 존재하지 않는 transcript_path → agent_message 미발행"
{
  nonexistent="/tmp/does_not_exist_dogam_test_$(date +%s%N).jsonl"
  before=$(stream_lines)

  run_hook "$nonexistent" "reviewer-sunsin"

  after=$(stream_lines)
  added=$(( after - before ))
  cleanup_needed="$added"

  if [ "$added" -ge 1 ]; then
    new_lines=$(last_n_lines "$added")
    if echo "$new_lines" | grep -q '"type":"agent_message"'; then
      assert_fail "Case 5" "없는 파일인데 agent_message가 emit됨"
    else
      assert_pass "Case 5"
    fi
  else
    assert_pass "Case 5"
  fi

  remove_last_n_lines "$cleanup_needed"
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
