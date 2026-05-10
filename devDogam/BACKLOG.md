# BACKLOG — devDogam Phase 1 보류 항목

본 문서는 Week 2 검수(이순신·척후) 시 발견되었으나 Phase 1 범위 밖으로 결정된 위험·미흡 사항을 추적합니다. Phase 2 진입 또는 별도 작업 시 우선순위 순으로 재검토합니다.

---

## 보류 항목

| # | 항목명 | 발견 시점 | 위협 종류 | 영향 추정 | 완화 방향 | 우선순위 |
|---|---|---|---|---|---|---|
| **A** | `/tmp/dogam_task_id` TOCTOU 가능성 | Week 2 검수 (2026-05-10) | 보안 (race condition) | 다중 사용자 환경 또는 호스트 공유 시 symlink 공격으로 임의 파일 쓰기 가능. 현재 단일 사용자 dev 환경에서는 낮음. | (1) `${TMPDIR:-/tmp}/devDogam_${USER}_${RANDOM}` 방식 격리 명명, (2) `umask 0077` 적용 및 권한 600 강제, (3) taskId 세션 공유 폐기 및 매 훅 호출마다 신규 생성 | **P2** |
| **B** | Next.js 16.2.1 / PostCSS CVE (npm audit) | Week 2 검수 (2026-05-10) | 보안 (DoS, XSS) | Next.js 9.3.4 계열 DoS + PostCSS <8.5.10 XSS via Unescaped `</style>`. Dev 환경 내부 사용 시 노출 면 최소. 공개 호스팅 또는 외부 입력 처리 시 위험. | (1) `npm audit fix --force`로 next 16.2.x 최신 패치 적용, (2) PostCSS 직접 dependency 추가하여 8.5.10+ 강제, (3) Phase 2 배포 검토 전 일괄 업그레이드 | **P1** |
| **C** | `.claude/settings.local.json` 권한 과다 누적 | Week 2 검수 (2026-05-10) | 보안 (과다 권한) | 다른 vibe_ws 하위 프로젝트의 bash/read 권한 60+개 누적. devDogam 자체와 무관한 잔여물. 기능에는 영향 없음, 최소 권한 원칙 위반. | (1) 다른 프로젝트 활성도 확인 후 사용 안 하는 권한 제거, (2) 프로젝트별 settings 분리 검토 (devDogam/.claude/settings.local.json 내장 가능성), (3) 권한 카탈로그 문서화 후 정기 정리 | **P2** |
| **D** | transcript_path 파싱 → 진짜 agent_message 이벤트 | β++ 시동 (2026-05-10) | 기능 미흡 | 현재는 라이프사이클 이벤트(agent_start/end/dispatch)를 합성 메시지로 말풍선화. 에이전트의 실제 발화는 보이지 않아 "조선왕조 개발실록"의 콘텐츠 가치가 낮음. | Claude Code의 transcript_path 훅 입력에서 assistant 메시지를 추출 → `agent_message` 이벤트로 emit. eventStore에 정상 흐름. page.tsx의 BUBBLE_EVENT_TYPES·synthesizeBubbleMessage 제거. | **P1** (Phase 2) |
| **E** | UserPromptSubmit 훅 → 진짜 task_start 이벤트 | β++ 시동 (2026-05-10) | 기능 미흡 | currentTask?.title이 항상 null → 두루마리 제목이 합성 "사건 진행 중…"으로만 표시. 임금의 진짜 명(prompt) 텍스트가 두루마리에 안 적힘. | UserPromptSubmit 훅 추가하여 prompt 텍스트로 task_start 이벤트 emit. page.tsx의 isActive 합성 제목 폴백 제거. | **P1** (Phase 2) |
| **F** | 도제 12 픽셀 자산 (β++ 후속) | β++ 시동 (2026-05-10) | 시각 미흡 | β++에서는 왕(king) + 매니저 4 = 5개 픽셀 자산만 제작. 도제 12명은 기존 placeholder 또는 색상 원형 유지. β++ 통과 후 사용자 평가·인스타 반응 보고 진행 결정. | 도제 12명 idle 32×32 4-frame 픽셀 자산 제작. characters.ts에 등록. CharacterAvatar에서 동일 패턴으로 표시. | **P1** (β++ 후속) |
| **G** | 도제 보고 choreography 정교화 | β++ 시동 (2026-05-10) | UX 미흡 | 도제 등장 → 매니저 옆 정렬 → 보고 → 퇴장의 부드러운 전환이 현재 단순 mount/unmount. β++에서는 기존 패턴 유지하고, 후속에서 Framer Motion 동선 + 이동·말풍선 타이밍 정교화. | Framer Motion variants로 도제 등장 위치(가장자리) → 매니저 옆 → 퇴장 동선 정의. 보고 말풍선과 이동 동기화. | **P1** (β++ 후속) |
| **H** | 어전 배경(일월오봉도) 디테일 정교화 | β++ 시동 (2026-05-10) | 시각 미흡 | β++에서는 SVG 그라디언트 + 5봉 실루엣 수준의 간단 배경만 제작. 추후 픽셀 그래픽 실측 일월오봉도 또는 layered parallax 도입 검토. | 픽셀 일월오봉도 자산 제작 (또는 SVG 디테일 추가). 해/달, 다섯 산봉우리, 적·청·소나무 모티프 강조. | **P2** |
| **I** | `selectLatestMessages` selector 본거지 결함 | β++ 시동 (2026-05-10), 기관도제 검수 | 코드 품질 (잠재 무한 루프 재발) | `state.events.filter(...).slice(-n)`이 매 호출 새 배열 반환 → Zustand 참조 동일성 검사가 항상 "변경됨"으로 판단해 무한 리렌더. page.tsx에서 useMemo 우회로 봉합했으나 다른 곳에서 selector 직접 사용 시 동일 결함 재발 가능. | (1) `selectLatestMessages` deprecated 처리 또는 삭제, (2) `reselect` `createSelector` 기반 메모이즈 selector로 교체, (3) eventStore 다른 selector도 동일 패턴 점검 | **P1** (Phase 2 또는 store 리팩토링 시) |
| **J** | SSE 연결 단절 시 `activeManagers`/`activeDojes` Set 누수 | β++ 시동 (2026-05-10), 기관도제 검수 | 정확성 (유령 active 상태) | `agent_dispatch` 처리에서 추가된 에이전트는 `agent_end` 수신 후 제거. 그러나 SSE 연결 도중 단절·훅 프로세스 비정상 종료 시 `agent_end` 누락 → 영원히 active. `setConnected(false)` 콜백이 Set 초기화 안 함. 두루마리 합성 제목·캐릭터 점등이 거짓 상태 표시 가능. | (1) `setConnected(false)` 시 `activeManagers`/`activeDojes` clear, (2) 또는 별도 `resetActive()` 액션을 SSE `onerror`/cleanup에서 호출, (3) Phase 2 task_start 도입과 동시에 처리 | **P1** (Phase 2) |
| **K** | TaskScroll step 타입·의미 명확화 | β++ 시동 (2026-05-10), 이순신 검수 | UX 모호 | 현재 `taskStep = { current, total }`이 *무엇을 세는지* 모호. currentTask 있을 땐 events 길이, 없을 땐 activeCount로 폴백 — 의미가 일관되지 않음. 사용자에게 진행도가 "1/1" "3/3"처럼 자기참조형으로 표시. | M2.x에서 step을 *이벤트 시퀀스 단계*로 재정의 (예: 정도전 분해 → 도제 구현 → 군관 테스트 → 이순신 검수 = 4단계). currentTask schema에 step 메타 추가. | **P2** (M2.x 통합 시) |
| **L** | 모바일 ChatBubble max-width 미정의 | β++ 검수 (2026-05-10), 이순신 검수 | 모바일 UX | 현재 ManagerCharacter 머리 위 ChatBubble의 `maxWidth: 240px` 고정. 640px 이하 작은 화면에서 옆 캐릭터 공간을 침범하거나 화면을 넘을 가능성. β++에서는 충분치 않으나 데스크톱 우선이라 보류. | (1) ChatBubble에 `maxWidth: "min(200px, 50vw)"` 미디어쿼리 또는 inline 적용, (2) 좁은 뷰포트에서 글자 크기 축소, (3) 인스타 reels 9:16 캡처 환경 점검 | **P2** (β++ 후속) |

---

## 재검토 절차

1. **P0 항목 없음** — Phase 1 완료로 즉시 처리 대상 없음.
2. **P1 항목 (B)** — Phase 2 진입 시 또는 호스팅 계획 수립 시 재검토. npm audit 결과 최신화 후 upgrade 경로 수립.
3. **P2 항목 (A, C)** — Phase 2 이후 또는 다중 사용자/다중 프로젝트 확산 시 검토. A는 호스트 공유 환경 진입 시, C는 다른 프로젝트 권한 정리와 함께 추진.

---

## 기록 이력

| 날짜 | 작성자 | 행동 |
|---|---|---|
| 2026-05-10 | 사관 (docs-sagwan) | 신규 작성. Week 2 검수 3개 항목 기록 |
| 2026-05-10 | 사관 (docs-sagwan) | β++ 시동 — D~H 5개 항목 추가 (transcript 파싱·UserPromptSubmit 훅·도제 픽셀·choreography·배경 디테일) |
| 2026-05-10 | 사관 (docs-sagwan) | β++ 시동 검수 — I·J·K 3개 항목 추가 (selectLatestMessages 결함·SSE Set 누수·TaskScroll step 의미) |
| 2026-05-10 | 메인 (이순신 검수 권고) | β++ 통합 검수 — L 1개 항목 추가 (모바일 ChatBubble max-width) |
