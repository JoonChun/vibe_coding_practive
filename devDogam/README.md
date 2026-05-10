# 개발도감 (Dev Dogam) — 조선왕조 개발실록

> 16명의 AI 에이전트가 어전회의를 열고 당신의 개발 작업을 함께 수행합니다.

조선의 명신 4인 — **정도전**·**장영실**·**이순신**·**정약용** — 과 그 휘하 도제 12명이 실시간으로 협업하는 모습을 시각화한 1인 개발자용 대시보드입니다. 단일 화면 *어전회의실*에서 16명이 살아 움직이며 당신의 임금(사용자)으로서의 명령을 함께 풀어나갑니다.

이 프로젝트는 **vibe_ws의 16 에이전트 시스템** (`.claude/agents/`)을 *실시간 시각화*하는 대표 시연 사례입니다.

## 현재 상태

**Phase 1 Week 1 완료** — 정적 골격 단계.

- [x] M1.1 Next.js + Tailwind + Zustand 스켈레톤
- [x] M1.2 16 캐릭터 placeholder SVG + 메타데이터
- [x] M1.3 정적 어전회의실 화면 (매니저 4인 노출)
- [x] M1.4 Framer Motion 기본 애니메이션 (idle 흔들기)
- ⏳ **Week 2**: SSE 연동 및 라이브 이벤트 통합
- ⏳ **Week 3**: 활성 상태 애니 + 도제 등장 + 광택 처리

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

## 실행

### 설치 및 개발 서버

```bash
npm install
npm run dev
```

`http://localhost:3000`에서 대시보드를 확인할 수 있습니다.

### 빌드 및 검사

```bash
npm run build
npm run lint
```

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
