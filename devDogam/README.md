# 개발도감 (Dev Dogam) — 조선왕조 개발실록

> 16명의 AI 에이전트가 어전회의를 열고 당신의 개발 작업을 함께 수행합니다.

조선의 명신 4인 — **정도전**·**장영실**·**이순신**·**정약용** — 과 그 휘하 도제 12명이 실시간으로 협업하는 모습을 시각화한 1인 개발자용 대시보드입니다. 단일 화면 *어전회의실*에서 16명이 살아 움직이며 당신의 임금(사용자)으로서의 명령을 함께 풀어나갑니다.

이 프로젝트는 **vibe_ws의 16 에이전트 시스템** (`.claude/agents/`)을 *실시간 시각화*하는 대표 시연 사례입니다.

## 현재 상태

**Phase 2 R 완료** — 실제 Claude 세션 연동 단계.

- [x] M1.1 ~ M1.4 Phase 1 완료 (정적 골격)
- [x] M2.1 ~ M2.2 Phase 2 A, B 완료 (SSE 클라이언트, Zustand)
- [x] M2.3 ~ M2.5 Phase 2 D, E 완료 (임금 입력창 실제 연동, transcript 파싱)
- [x] **Phase 2 R**: 임금 입력 → tmux → 메인 Claude 세션으로 실제 명령 전달 ✅
- ⏳ **Phase 3**: 활성 상태 애니 + 도제 실시간 등장
- ⏳ **Phase 4**: 말풍선 + 콘텐츠 캡처 최적화

자세한 진행 상황은 `PHASE-1-SPEC.md`를 참고하세요.

## 기술 스택

| 영역 | 선택 |
|---|---|
| 프레임워크 | Next.js 16 (App Router) |
| 언어 | TypeScript (strict) |
| 스타일 | Tailwind CSS 4 |
| 상태 관리 | Zustand |
| 애니메이션 | Framer Motion 12+ |
| 이벤트 | Server-Sent Events (SSE) |
| 파일 감시 | `chokidar` |

## 빠른 시작 (Quick Start)

### 사전 요구사항

- **Node.js 20+**, npm 10+
- **tmux 3.x 이상** (Linux/WSL2/macOS)
- **Claude Code CLI** 인증 완료 (`claude` 명령어 사용 가능)

### 시연 실행 (3단계)

#### 1단계: 메인 Claude 세션 기동

첫 번째 터미널에서:

```bash
cd devDogam/hooks
./start-reels-session.sh
```

이 스크립트는:
- 새 tmux 세션 `dogam-YYYYMMDD-HHMMSS` 생성
- **좌측 pane**: 메인 Claude 에이전트 로비 (플래너·구현자·검수자·발산가 기다리는 중)
- **우측 pane**: 도제 출진 기록부 (도제들의 작업 로그 실시간 출력)

#### 2단계: Next.js 개발 서버 시작

두 번째 터미널 (또는 tmux 새 창)에서:

```bash
cd devDogam
npm install  # 첫 실행 시만
npm run dev
```

#### 3단계: 임금 명령 입력

브라우저에서 `http://localhost:3000` 접속 → 화면 하단 🤴 **임금 입력창** → 명령 입력 → **Enter**

**예시:**
```
내게 BMI 계산기를 만들어 주거라.
```

입력하면:
1. 메인 Claude 세션(좌측 pane)으로 프롬프트 자동 전달
2. 정도전이 계획 시작 → 도제들 출진
3. 우측 pane에 도제 이름과 작업 기록 실시간 출력
4. 대시보드에서 캐릭터 애니메이션 (구현 중)

### 설치 및 개발

```bash
npm install
npm run build
npm run lint
```

### 환경 변수 설정 (`.env.local`)

**파일 생성:**

```bash
cp .env.local.example .env.local
```

**옵션:**

| 변수 | 값 | 설명 |
|---|---|---|
| `NEXT_PUBLIC_KING_INPUT_MODE` | `real` (기본) | 실제 tmux 세션으로 프롬프트 인젝션. `start-reels-session.sh`로 메인 Claude 기동 필수 |
| `NEXT_PUBLIC_KING_INPUT_MODE` | `mock` | 디버깅·스크린샷 모드. fetch 호출 없이 입력창만 비움. tmux 불필요 |

### 정상 작동 확인

✅ 좌측 pane에 `>>` 프롬프트 표시
✅ 우측 pane에 "출진 기록부" 헤더 표시
✅ `localhost:3000` 대시보드 로드 완료
✅ 입력창 🤴 아이콘 표시

### 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| "도감 세션이 열려 있지 않습니다" 토스트 | 메인 Claude 세션 미실행 | `./start-reels-session.sh` 다시 실행 |
| "tmux를 찾을 수 없습니다" | tmux 미설치 | `apt install tmux` (Linux) / `brew install tmux` (macOS) |
| "명을 너무 빠르게 내리셨습니다" | rate limit (1초) | 2초 이상 간격 두고 입력 |
| 입력창이 회색이고 비활성 | `NEXT_PUBLIC_KING_INPUT_MODE=mock` 설정 | `.env.local`에서 `real`로 변경 |
| 우측 pane이 열리지 않음 | 기존 tmux 세션 충돌 | 터미널 재시작 또는 `tmux kill-session -t dogam-*` |

## 폴더 구조

```
devDogam/
├── src/
│   ├── app/
│   │   ├── layout.tsx           # 어전회의실 레이아웃
│   │   ├── page.tsx             # 메인 화면
│   │   └── api/events/route.ts  # SSE 엔드포인트
│   ├── components/
│   │   ├── characters/          # 캐릭터 아바타 (매니저·도제)
│   │   ├── chat/                # 말풍선 컴포넌트
│   │   ├── scroll/              # 두루마리 (진행도)
│   │   └── input/               # 임금 입력창
│   ├── lib/
│   │   ├── characters.ts        # 16 캐릭터 메타데이터
│   │   └── eventStream.ts       # SSE 클라이언트
│   ├── stores/
│   │   └── eventStore.ts        # Zustand 상태 관리
│   └── types/
│       └── events.ts            # AgentEvent 타입
├── public/characters/           # SVG placeholder
├── hooks/                        # Claude Code 훅 스크립트
├── events/                       # 이벤트 스트림 파일 (커밋 안 함)
├── prd.md                        # 제품 요구사항
├── PHASE-1-SPEC.md             # Phase 1 구현 스펙
└── README.md                     # 이 파일
```

## 마일스톤 진행률

| 마일스톤 | 상태 | 설명 |
|---------|------|------|
| **Week 1** | ✅ 완료 | 정적 골격 (Next.js, 스켈레톤, placeholder 캐릭터, idle 애니) |
| **Week 2** | ⏳ 진행 중 | 동적 통합 (SSE, 이벤트 상태, Claude Code 훅, 라이브 시험) |
| **Week 3** | ⏳ 예정 | 광택 (활성·발화 애니, 도제 등장, 말풍선 스타일, 콘텐츠 캡처) |

## 참고 문서

- [`prd.md`](./prd.md) — 전체 프로젝트 비전, 16인 캐스팅, 5단계 Phase 정의
- [`PHASE-1-SPEC.md`](./PHASE-1-SPEC.md) — Phase 1 상세 구현 스펙, 이벤트 스키마, 화면 명세

## 에이전트 시스템

이 프로젝트는 vibe_ws의 **16 에이전트 협업 시스템**의 핵심 시연 사례입니다. 자세한 라우팅 규칙은 `CLAUDE.md`의 *에이전트 라우팅 규칙* 섹션을 참고하세요.

---

Built by the 조선왕조 개발실록 팀 — 정도전·장영실·이순신·정약용 및 휘하 도제 12인.
