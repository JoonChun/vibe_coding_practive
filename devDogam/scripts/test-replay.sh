#!/usr/bin/env bash
# ── SSE replay 통합 시험 (옵션 C) ─────────────────────────────────────────────
# dev 서버(http://localhost:3000)가 실행 중일 때 실제 SSE 응답을 검증.
# 실행 권한: chmod +x scripts/test-replay.sh
# 실행: bash scripts/test-replay.sh
#
# 검증 항목:
#   1. fixture 10줄 작성 → SSE 응답에 data: 라인 10개 포함
#   2. data: 라인의 내용이 기록한 JSON과 일치
#   3. ping(: ping) 은 data: 가 아니므로 카운트 제외
#   4. stream.jsonl 원복
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── 경로 설정 ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STREAM_DIR="$PROJECT_DIR/events"
STREAM_FILE="$STREAM_DIR/stream.jsonl"
BACKUP_FILE="$STREAM_DIR/stream.jsonl.bak"
SSE_URL="http://localhost:3000/api/events"
FIXTURE_COUNT=10

PASS=0
FAIL=0

log_pass() { echo "[PASS] $1"; ((PASS++)); }
log_fail() { echo "[FAIL] $1"; ((FAIL++)); }
log_info() { echo "[INFO] $1"; }

# ── dev 서버 확인 ─────────────────────────────────────────────────────────────
log_info "dev 서버 확인: $SSE_URL"
if ! curl -s --max-time 2 "$SSE_URL" > /dev/null 2>&1; then
  echo ""
  echo "[SKIP] dev 서버가 응답하지 않습니다 (localhost:3000)."
  echo "       'npm run dev' 로 서버를 먼저 기동한 뒤 재실행하시오."
  echo ""
  exit 0
fi
log_info "dev 서버 응답 확인됨."

# ── stream.jsonl 백업 ─────────────────────────────────────────────────────────
mkdir -p "$STREAM_DIR"
if [[ -f "$STREAM_FILE" ]]; then
  cp "$STREAM_FILE" "$BACKUP_FILE"
  log_info "stream.jsonl 백업 완료: $BACKUP_FILE"
else
  log_info "stream.jsonl 없음 — 신규 생성 후 시험."
fi

# ── 정리 훅: 항상 원복 ─────────────────────────────────────────────────────────
cleanup() {
  if [[ -f "$BACKUP_FILE" ]]; then
    mv "$BACKUP_FILE" "$STREAM_FILE"
    log_info "stream.jsonl 원복 완료."
  else
    # 원본이 없었으면 생성된 fixture 삭제
    rm -f "$STREAM_FILE"
    log_info "stream.jsonl 제거 완료 (원본 없었음)."
  fi
}
trap cleanup EXIT

# ── fixture 작성 ───────────────────────────────────────────────────────────────
log_info "fixture ${FIXTURE_COUNT}줄 작성 → $STREAM_FILE"
: > "$STREAM_FILE"  # 파일 초기화
for i in $(seq 1 "$FIXTURE_COUNT"); do
  echo "{\"id\":\"fixture-${i}\",\"type\":\"test\",\"seq\":${i}}" >> "$STREAM_FILE"
done
log_info "fixture 작성 완료."

# ── SSE 응답 캡처 (3초) ───────────────────────────────────────────────────────
log_info "SSE 캡처 시작 (timeout 3s) …"
SSE_RESPONSE="$(timeout 3 curl -N -s "$SSE_URL" 2>/dev/null || true)"

if [[ -z "$SSE_RESPONSE" ]]; then
  log_fail "SSE 응답이 비어있음."
else
  log_info "SSE 응답 수신됨."
fi

# ── 검증 1: data: 라인 개수 ───────────────────────────────────────────────────
DATA_COUNT="$(echo "$SSE_RESPONSE" | grep -c '^data:' || true)"
log_info "data: 라인 수: $DATA_COUNT (기대: $FIXTURE_COUNT)"
if [[ "$DATA_COUNT" -eq "$FIXTURE_COUNT" ]]; then
  log_pass "data: 라인 수 = $FIXTURE_COUNT"
else
  log_fail "data: 라인 수 불일치 (실제: $DATA_COUNT, 기대: $FIXTURE_COUNT)"
fi

# ── 검증 2: fixture id 포함 확인 (전체) ───────────────────────────────────────
MATCH_COUNT=0
for i in $(seq 1 "$FIXTURE_COUNT"); do
  if echo "$SSE_RESPONSE" | grep -q "\"fixture-${i}\""; then
    ((MATCH_COUNT++))
  fi
done
log_info "id 매칭 수: $MATCH_COUNT / $FIXTURE_COUNT"
if [[ "$MATCH_COUNT" -eq "$FIXTURE_COUNT" ]]; then
  log_pass "fixture id 전체 포함 확인 ($FIXTURE_COUNT/$FIXTURE_COUNT)"
else
  log_fail "fixture id 일부 누락 ($MATCH_COUNT/$FIXTURE_COUNT)"
fi

# ── 검증 3: ping 라인은 data: 아님 확인 ──────────────────────────────────────
PING_COUNT="$(echo "$SSE_RESPONSE" | grep -c '^: ping' || true)"
log_info "ping 라인 수: $PING_COUNT (data: 에 포함 X 확인)"
if [[ "$DATA_COUNT" -eq "$FIXTURE_COUNT" ]]; then
  log_pass "ping 라인이 data: 카운트에 포함되지 않음"
else
  log_fail "ping 라인이 data: 에 섞여 카운트 오염 가능성"
fi

# ── 결과 요약 ─────────────────────────────────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
echo "  통합 시험 결과: PASS=$PASS  FAIL=$FAIL"
echo "────────────────────────────────────────"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
