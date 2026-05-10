# devDogam 훅 (Hook) 가이드

Claude Code가 서브에이전트를 호출할 때 자동으로 `devDogam/events/stream.jsonl`에 이벤트를 기록하는 스크립트.

## 개요

- **`on-subagent-start.sh`**: 에이전트 호출 시작 → `agent_start` 이벤트 기록
- **`on-subagent-stop.sh`**: 에이전트 응답 완료 → `agent_end` 이벤트 기록

이 훅들은 `.claude/settings.local.json`에 등록되어 자동 활성화됨.

## 사전 요건

### 필수 도구

- `bash` — 대부분의 Unix/Linux 환경에 기본 포함
- (선택) `jq` — JSON 파싱용. 없으면 `grep` 폴백으로 자동 전환

**jq 설치 (선택)**:
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

jq가 없어도 동작함. 기본적으로 `grep`을 사용한 단순 파싱으로 충분.

### 파일 시스템

- `/home/joon/vibe_ws/devDogam/events/` — JSONL 파일 쓰기 권한 필요
- `${TMPDIR:-/tmp}/` — taskId 세션 파일 쓰기 권한 필요

## 자동 활성화

`.claude/settings.local.json`에 다음이 등록되면 자동 작동:

```json
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "/home/joon/vibe_ws/devDogam/hooks/on-subagent-start.sh"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "/home/joon/vibe_ws/devDogam/hooks/on-subagent-stop.sh"
          }
        ]
      }
    ]
  }
}
```

매 서브에이전트 호출 시 자동으로 훅 스크립트 실행.

## 실행 권한

스크립트는 `chmod +x`로 실행 가능하게 설정되어 있음:

```bash
ls -la /home/joon/vibe_ws/devDogam/hooks/
# -rwxr-xr-x on-subagent-start.sh
# -rwxr-xr-x on-subagent-stop.sh
```

## 동작 원리

### stdin에서 에이전트 이름 추출

Claude Code는 호출 시 JSON 형식 메타데이터를 stdin으로 전달. 훅이 다중 폴백으로 파싱:

```bash
# 시도 순서: agent_name → agentName → tool_name → "unknown"
```

예시 input:
```json
{"agent_name":"planner-dojeon"}
```

또는:
```json
{"agentName":"planner-dojeon"}
```

### 이벤트 ID & 타임스탬프

- **ID**: `/proc/sys/kernel/random/uuid` 또는 fallback (실패 시 `date +%s%N`)
- **timestamp**: Unix milliseconds (정확히 13자리)
  - v2.3까지 버그: `date +%s%3N` 결과에 `000` 추가로 16자리 발생
  - v2.4+: 자릿수 검증으로 안전성 강화. GNU date 미지원 환경도 대응.

WSL2/Linux에서 동작 확인됨.

### 세션별 taskId

같은 Claude Code 세션에서 호출된 에이전트들은 **동일한 taskId**를 공유:

```bash
# /tmp/dogam_task_id (또는 $TMPDIR)
task-a1b2c3d4

# 이 세션의 모든 에이전트가 이 ID로 묶임
```

세션 종료 시 TMPDIR이 정리되면 다음 세션에서 새 ID 생성.

## 디버깅

### 라이브 모니터링

```bash
tail -f /home/joon/vibe_ws/devDogam/events/stream.jsonl
```

실시간으로 기록되는 JSONL 라인을 볼 수 있음.

### 훅 에러 로그

훅 실패 시 (조용하지만) 다음에 기록:

```bash
cat /home/joon/vibe_ws/devDogam/events/hook-errors.log
```

### 수동 테스트

```bash
# start 훅 테스트
echo '{"agent_name":"planner-dojeon"}' | /home/joon/vibe_ws/devDogam/hooks/on-subagent-start.sh

# stream.jsonl 확인
cat /home/joon/vibe_ws/devDogam/events/stream.jsonl
# {"id":"<uuid>","timestamp":<ms>,"type":"agent_start","agentName":"planner-dojeon","taskId":"task-..."}

# 종료 코드 확인
echo '{}' | /home/joon/vibe_ws/devDogam/hooks/on-subagent-stop.sh; echo "exit=$?"
# exit=0 (항상 성공)
```

## 알려진 한계 (Phase 1)

### parentAgent 미기록

현재는 `agent_start`/`agent_end` 이벤트만 기록. 매니저→도제 위임 관계는 다음 방식으로 추론:

1. **시간 인접성 휴리스틱**: 같은 taskId 내 시간상 인접한 에이전트들 = 위임 관계
2. (Phase 2) 매니저 시스템 프롬프트에 "위임 시 `[DISPATCH: 도제-이름]` 마커 출력" 추가

### taskId 누적

세션 간 파일이 정리되지 않으면 `dogam_task_id` 파일이 남아 같은 ID가 재사용될 수 있음. Phase 1에서는 단순화로 수용. 다음 방법으로 수동 reset:

```bash
rm /tmp/dogam_task_id  # 또는 $TMPDIR/dogam_task_id
```

### agentName 추출 (개선됨 v2.4)

v2.3까지: stdin JSON이 예기치 않은 형식이면 `agentName: "unknown"` 기록.
v2.4+: Claude Code 공식 문서 `agent_type` 필드 추가 (폴백 최우선). 폴백 순서: `agent_type` → `agent_name` → `agentName` → `tool_name` → `"unknown"`.

## 비활성화

`.claude/settings.local.json`에서 `hooks` 키 전체 삭제 또는 주석화:

```json
{
  // "hooks": { ... }  // 주석화
  "permissions": { ... }
}
```

그 후 Claude Code 재시작. 훅은 더 이상 작동하지 않음.

## 더 알아보기

- 전체 설명: `PHASE-1-SPEC.md` §5
- 이벤트 스키마: `PHASE-1-SPEC.md` §4
