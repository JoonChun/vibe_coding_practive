# Phase 1 — 어전회의실 (Royal Court) MVP 구현 스펙

> 16 에이전트 협업을 *실시간으로 보이게* 만드는 단일 화면 대시보드. PRD §5.3의 구현 스펙.

| 항목 | 값 |
|---|---|
| 기간 | 2~3주 |
| 검증 가설 | H3 (시각화 = 노이즈 X 정보 ✓), H4 (인스타 인게이지먼트 ↑) |
| 선행 조건 | Phase 0b 통과 ✅ (커밋 `f2dc2bc` BMI 시연으로 확인됨) |

---

## 1. Goal & Non-goal

### Goal
- 사용자(임금)가 작업을 명하면, 화면에서 16명이 *살아 있는 듯* 움직이는 모습을 본다
- 인스타 reels로 캡처할 수 있는 명장면 *최소 1개* 만들어진다
- 매니저-도제 위계가 *시각적으로* 드러난다 (도제 = 매니저 옆 작은 캐릭터)

### Non-goal (★ 절대 만들지 말 것)
- ❌ Tab 2/3/4 (증거실·사건추적도·어서각) — Phase 2
- ❌ Monaco Editor — Phase 2
- ❌ LangGraph — Phase 2
- ❌ Lottie 애니메이션 — Phase 2 (Framer Motion + 정적 SVG 만)
- ❌ 사용자가 UI에서 캐릭터·MBTI 편집 — Phase 2
- ❌ 리플레이·트로피 — Phase 2
- ❌ FastAPI·WebSocket·PostgreSQL — Phase 2

## 2. 기술 스택 (고정)

| 영역 | 선택 | 사유 |
|---|---|---|
| 프레임워크 | Next.js 16 (App Router) | 레포 컨벤션 (`all-in-one_calculator`와 동일) |
| 언어 | TypeScript (strict) | 동일 |
| 스타일 | Tailwind CSS 4 | 동일 |
| 애니 | Framer Motion 12+ | PRD 명시 |
| 상태 | Zustand | 레포 컨벤션 |
| 파일 감시 | `chokidar` 또는 `fs.watch` | SSE 푸시용 |
| 이벤트 전송 | Server-Sent Events (SSE) | 단방향 read-only에 충분 |
| 테스트 | Vitest + Testing Library | 레포 컨벤션 |

## 3. 폴더 구조

```
devDogam/
├── prd.md                          (이미 있음)
├── PHASE-1-SPEC.md                 (이 문서)
├── package.json                    (신규)
├── next.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── src/
│   ├── app/
│   │   ├── layout.tsx              어전회의실 레이아웃
│   │   ├── page.tsx                Tab 1 어전회의실 메인
│   │   ├── globals.css
│   │   └── api/
│   │       └── events/
│   │           └── route.ts        SSE 엔드포인트 (events/stream.jsonl 감시)
│   ├── components/
│   │   ├── characters/
│   │   │   ├── CharacterAvatar.tsx     공통 아바타 (placeholder SVG + emoji)
│   │   │   ├── ManagerCharacter.tsx    매니저 4인 (큰 사이즈)
│   │   │   └── DojeCharacter.tsx       도제 12인 (작은 사이즈, 매니저 옆)
│   │   ├── chat/
│   │   │   └── ChatBubble.tsx          만화풍 말풍선 (캐릭터 색상 테두리)
│   │   ├── scroll/
│   │   │   └── TaskScroll.tsx          두루마리 = 작업 진행도
│   │   └── input/
│   │       └── KingInput.tsx           임금 입력창 (지금은 disabled placeholder)
│   ├── lib/
│   │   ├── characters.ts               16 캐릭터 메타데이터 (이름·색상·매니저)
│   │   └── eventStream.ts              SSE 클라이언트 래퍼
│   ├── stores/
│   │   └── eventStore.ts               이벤트·활성 캐릭터 상태
│   └── types/
│       └── events.ts                   AgentEvent 타입
├── public/
│   └── characters/
│       └── (16 placeholder SVG — 단순 원 + emoji + 색상)
├── hooks/                              Claude Code 훅 스크립트
│   ├── on-subagent-start.sh
│   ├── on-subagent-stop.sh
│   └── README.md                       훅 설치·디버깅 가이드
├── events/
│   ├── .gitignore                      *.jsonl 무시
│   └── stream.jsonl                    실행 시 생성 (커밋 X)
└── README.md                           실행·개발 가이드 (신규)
```

## 4. 이벤트 스키마

### 4.1 `AgentEvent` 타입 (`src/types/events.ts`)

```ts
export type AgentEventType =
  | "task_start"      // 임금 명령 시작
  | "task_end"        // 작업 종료
  | "agent_start"     // 에이전트 호출됨
  | "agent_message"   // 에이전트가 한 번 발화
  | "agent_end"       // 에이전트 응답 완료
  | "agent_dispatch"; // 매니저가 도제 위임

export interface AgentEvent {
  id: string;              // ulid
  timestamp: number;       // Unix ms
  type: AgentEventType;
  agentName: string;       // "planner-dojeon" 등
  parentAgent?: string;    // 위임 시 매니저 이름
  taskId: string;          // 한 작업 단위 묶음
  message?: string;        // 짧은 발화 요약 (말풍선용)
  metadata?: Record<string, unknown>;
}
```

### 4.2 JSON Lines 형식 (`devDogam/events/stream.jsonl`)

각 줄 1개 이벤트, append-only:
```
{"id":"01J...","timestamp":1746789000123,"type":"task_start","agentName":"king","taskId":"t-01","message":"BMI 계산기 추가하라"}
{"id":"01J...","timestamp":1746789001500,"type":"agent_start","agentName":"planner-dojeon","taskId":"t-01"}
{"id":"01J...","timestamp":1746789015000,"type":"agent_message","agentName":"planner-dojeon","taskId":"t-01","message":"단계별 설계 올립니다."}
{"id":"01J...","timestamp":1746789015800,"type":"agent_dispatch","agentName":"implementer-yeongsil","parentAgent":"planner-dojeon","taskId":"t-01"}
...
```

## 5. Claude Code 훅 설계

### 5.1 `.claude/settings.local.json` 추가

```json
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/devDogam/hooks/on-subagent-start.sh"
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
            "command": "$CLAUDE_PROJECT_DIR/devDogam/hooks/on-subagent-stop.sh"
          }
        ]
      }
    ]
  }
}
```

### 5.2 훅 스크립트 책무

- 환경변수 또는 stdin에서 에이전트 이름·메시지 받아 `devDogam/events/stream.jsonl`에 1줄 append
- ULID·timestamp는 스크립트가 생성
- `agentDispatch` 같은 부가 이벤트는 휴리스틱 또는 단순 무시 (Phase 2에서 정밀화)
- **실패해도 Claude Code 본 작업을 막지 않게** silent fail (`|| true`)

### 5.3 훅 한계 (현재 알려진)

Claude Code 훅 시스템에서 *부모-자식 위임 관계*가 직접 노출되지 않을 수 있음. 그 경우:
- (a) `agent_start` 이벤트만 기록하고, dispatch는 *시간적 인접성*으로 추론 (frontend에서)
- (b) 또는 매니저 시스템 프롬프트에 "위임 시 표준 마커 출력" 추가 → 훅이 메시지 파싱

→ 통신도제·정도전이 검토 후 결정.

## 6. 화면 명세

### 6.1 레이아웃

```
┌───────────────────────────────────────────────────────────────┐
│ 📜 두루마리 (TaskScroll)                                      │
│ "사건: BMI 계산기 추가  |  단계 3/6 진행 중"                  │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│   📐         🔧         ⚓         💡                          │
│  정도전    장영실    이순신    정약용                            │
│  (blue)   (orange)   (red)    (green)                         │
│  [active]                                                     │
│   │                                                           │
│   └─ 📋 도제 (호조낭청 등 작은 캐릭터 발밑 등장)                │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│  💬 정도전: "임금께 여쭙고자 하는 것: ..."        [blue 테두리] │
│  💬 호조낭청: "P0 셋을 우선..."                 [cyan 테두리]   │
│  ... (스크롤 가능 채팅 로그)                                   │
├───────────────────────────────────────────────────────────────┤
│  🤴 임금 입력창 (Phase 1: disabled placeholder)               │
└───────────────────────────────────────────────────────────────┘
```

### 6.2 캐릭터 표시 규칙

- **매니저** (`ManagerCharacter`): 64×64px placeholder SVG, 항상 4명 노출
- **도제** (`DojeCharacter`): 40×40px placeholder SVG, 매니저 발밑 절반 겹침
- **활성 표시**:
  - idle: 미세 흔들기 (Framer Motion `animate={{ y: [0, -2, 0] }}`, 2초 루프)
  - active (`agent_start` 발생): 색상 ring + 작은 점프
  - speaking (`agent_message` 발생): 0.3초 강조 점프 + 말풍선 페이드인
- **위계 시각**: 도제는 매니저보다 *작고*, 매니저 위치 기준 *오프셋*으로 등장
- **빈도**: 매니저는 기본 노출. 도제는 호출됐을 때만 노출, 종료 후 페이드아웃

### 6.3 말풍선

- 캐릭터 색상으로 테두리 (`border-2 border-{color}-500`)
- 말풍선 꼬리는 화자 캐릭터 방향
- 최신 5개만 화면 노출, 이전은 스크롤
- 매니저 = 큰 말풍선, 도제 = 작은 말풍선

### 6.4 두루마리 (TaskScroll)

- 한지 베이지 배경 + 명조체
- 현재 작업명·진행 단계 (있다면) 표시
- 작업 종료 시 "사건 종결" 도장 애니 (Phase 2 가까울수록 정교화)

## 7. 캐릭터 placeholder 전략

Phase 1는 **AI 이미지 생성 X**. 단순 SVG로 충분.

각 캐릭터 = 색 채워진 원 + 한가운데 emoji + 이름 라벨:

```tsx
<svg width="64" height="64">
  <circle cx="32" cy="32" r="30" fill="var(--color-character)" />
  <text x="32" y="40" textAnchor="middle" fontSize="32">📐</text>
</svg>
<div className="text-xs mt-1">정도전</div>
```

후일 Phase 1.5 또는 Phase 2에서 Nano Banana / Leonardo 결과물로 교체. 그때 SVG → PNG 단순 swap.

## 8. 캐릭터 메타데이터 (`src/lib/characters.ts`)

```ts
export interface CharacterMeta {
  name: string;        // agent name (frontmatter)
  displayName: string; // 정도전
  emoji: string;       // 📐
  color: string;       // tailwind class color (blue / orange / ...)
  hex: string;         // #2C5F8D
  manager: boolean;    // 매니저 여부
  parent?: string;     // 도제의 경우 매니저 name
}

export const CHARACTERS: Record<string, CharacterMeta> = {
  "planner-dojeon": { displayName: "정도전", emoji: "📐", color: "blue", hex: "#2C5F8D", manager: true },
  "planning-hojo": { displayName: "호조낭청", emoji: "📋", color: "cyan", hex: "#06b6d4", manager: false, parent: "planner-dojeon" },
  // ... 16개 다 정의
};
```

## 9. 마일스톤 (3주)

### Week 1 — 정적 골격
- **M1.1** Next.js 16 + Tailwind 4 + Zustand 스켈레톤 (1일)
- **M1.2** 16 character placeholder SVG + `characters.ts` 메타데이터 (1일)
- **M1.3** 정적 어전회의실 화면 (4 매니저 노출, 도제 미연결, 말풍선 mock) (2일)
- **M1.4** Framer Motion idle 흔들기 (1일)

### Week 2 — 동적 통합
- **M2.1** 이벤트 타입 + Zustand store (1일)
- **M2.2** SSE API route + JSON 파일 감시 (`chokidar` 또는 `fs.watch`) (1일)
- **M2.3** Claude Code 훅 스크립트 + `.claude/settings.local.json` 설정 (1일)
- **M2.4** 라이브 통합 시험 — 메인 세션에서 작업 명하고 화면 반응 확인 (1일)

### Week 3 — 광택 (선택)
- **M3.1** 활성·발화 애니 (점프·페이드) (1일)
- **M3.2** 도제 등장·퇴장 애니 (1일)
- **M3.3** 말풍선 만화풍 스타일링 (반나절)
- **M3.4** 인스타 reels 1편 캡처 + 게시 (반나절)

## 10. 검수 항목 (이순신·척후 점검 대상)

- [ ] `tsconfig.json strict: true`, lint 통과
- [ ] `npm run build` 성공
- [ ] `devDogam/events/` 디렉토리가 `.gitignore`에 포함 (커밋 X)
- [ ] SSE 연결이 *재연결 가능* (네트워크 끊김 시 자동 재시도)
- [ ] 16 캐릭터 메타데이터 누락 없음 (16/16)
- [ ] 매니저·도제 색상이 `prd.md` §4.1~4.5와 일치
- [ ] 말풍선이 *최신 5개*만 노출 (메모리 누수 방지)
- [ ] 훅 스크립트 실패 시 Claude Code 본 작업 막지 않음 (silent fail)
- [ ] 접근성: ARIA·키보드 네비 (입력창 disabled여도 라벨 명시)
- [ ] 모바일 반응형 (인스타 reels는 세로 9:16)
- [ ] **메인 dev 서버 라이브 점검**: `npm run dev` 띄운 상태에서 브라우저 콘솔 0 에러 확인. 빌드·테스트 통과만으론 부족 — 런타임 hydration 에러나 무한 루프는 빌드 시 안 잡힘. (*사유*: 임시 hotfix 3건이 모두 빌드 통과 후에야 사용자 첫 로드에서 드러남)
- [ ] **메인 세션 1회 작업 트리거 후 시각 변화 확인**: 메인 Claude 세션에서 작업 1건을 트리거하여 (a) 매니저 캐릭터 점등, (b) 말풍선 1회 이상 출현, (c) 두루마리 제목 변화, (d) 도제 등장(해당 작업 도제 영역일 때) 확인. 정적 시험만으론 통합 결함을 못 잡음. (*사유*: 임시 hotfix 3건이 모두 빌드 통과 후에야 사용자 첫 로드에서 드러남)

## 11. Phase 1 통과 기준 (PRD §5.3)

- [ ] 16명의 협업이 *실시간으로* 보임
- [ ] 도제 호출 시 매니저 발밑에 *작은 도제 캐릭터*가 등장
- [ ] 인스타 reels로 만들 가치 있는 *명장면 1개 이상* 캡처

## 12. 위험·완화

| 위험 | 완화 |
|---|---|
| Claude Code 훅 시스템이 부모-자식 관계 미노출 | 시간 인접성 휴리스틱 + 매니저 시스템 프롬프트에 마커 추가 |
| 캐릭터 placeholder가 인스타 매력 부족 | Week 3에 약간의 일러 보강. 본격 일러는 Phase 2 |
| Next.js 16 + Tailwind 4가 호환 이슈 | 문제 시 Next.js 15 + Tailwind 3 폴백 (calculator와 동일 버전) |
| `events/stream.jsonl` 비대화 | 작업 종료 시 별도 archive 파일로 옮김 + stream.jsonl 비움 |
| SSE 연결 끊김 | 자동 재연결 + last-event-id 사용 |

## 13. 호출 라인 (메인 세션 시동)

```
개발도감 Phase 1 착수.
devDogam/PHASE-1-SPEC.md 참고하여 진행.

순서:
1. 정도전께 마일스톤 M1.1~M1.4 (Week 1)을 단계 분해 청한다.
2. 정약용·화공께 어전회의실 시각 컨셉 발산 청한다 (placeholder를 어떻게 살릴지).
3. 도화서 화원이 §6 레이아웃을 와이어프레임으로 구체화.
4. 단청도제·통신도제·기관도제가 M1.1부터 시행.
5. 토목도제가 .claude/settings.local.json 훅 설정 (M2.3 시점).
6. 군관·이순신이 M2.4까지의 통과 기준 (§10·11) 검수.

Week 1 (M1.1~M1.4)부터 진행하시오.
```
