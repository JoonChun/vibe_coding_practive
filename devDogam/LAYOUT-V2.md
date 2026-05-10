# devDogam β++ 어전 도열 레이아웃 (LAYOUT-V2)

> 도화서 화원이 그려 올린 와이어프레임. 단청도제·기관도제가 보고 그대로 지을 수 있도록 좌표·크기·흐름을 명기함.

---

## 1. 전체 화면 ASCII 와이어프레임

아래 그림은 데스크톱 기준 (1280×800px 내외). 세로 5단으로 구획함.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [청]     [적]     [황]     [백]     [흑]    개발도감(開發都監)    ● 실시간   │  ← 단청 헤더 (48px)
├─────────────────────────────────────────────────────────────────────────────┤
│  📜 사건: BMI 계산기 추가      ████████░░  단계 8/10 진행 중                 │  ← 두루마리 (64px)
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   [💬정도전]  [💬정약용]   🌄🌕🌄   [💬장영실]  [💬이순신]                  │  ← 말풍선 (캐릭터 머리 위)
│                           ░░░░░░░                                           │
│   ┌──────┐  ┌──────┐   ┌────────┐   ┌──────┐  ┌──────┐                   │
│   │  📐  │  │  💡  │   │  🤴    │   │  🔧  │  │  ⚓  │                   │
│   │정도전│  │정약용│   │  옥좌  │   │장영실│  │이순신│                   │
│   └──────┘  └──────┘   └────────┘   └──────┘  └──────┘                   │
│       │                                  │                                  │
│    [도제]                             [도제]                                │  ← 도제 등장 영역
│   📋 🖋️ 📜                           🎨 ⚙️ 🏗️ 📡                          │
│                                                                             │
│ ← 도제 등장 방향 (좌 가장자리)           도제 등장 방향 (우 가장자리) →     │
│                       일월오봉도 배경                                        │  ← 어전 영역 (flex-1)
├─────────────────────────────────────────────────────────────────────────────┤
│  🤴  [ 임금의 명이 이르시면…                                        [전송] ] │  ← KingInput (56px)
└─────────────────────────────────────────────────────────────────────────────┘
```

### 어전 영역 확대 — 캐릭터 좌표 명세

```
     0%                  25%           50%          75%               100%  (가로 %)
      │                   │             │             │                  │
 10%  │                   │             │             │                  │
      │                                 │                                │
      │                           ┌──────────┐                          │  ← 일월오봉도 배경 상단
 20%  │                           │  🌕  ☀️  │                          │     달(좌)·해(우) 그라디언트 원
      │                           │          │                          │
 30%  │                           │  ^^^↑↑↑  │                          │     5봉 실루엣 (삼각형×5)
      │                           │ 봉봉봉봉봉│                          │
      │  💬도전      💬약용        │  [🤴옥좌]│   💬영실       💬순신     │  ← 말풍선 (캐릭터 머리 위)
 40%  │                           │          │                          │
      │  ┌────┐      ┌────┐       │  ┌─────┐ │    ┌────┐      ┌────┐   │
 45%  │  │ 📐 │      │ 💡 │       │  │ 🤴  │ │    │ 🔧 │      │ ⚓ │   │  ← 매니저 4인 + 왕 (64px 픽셀)
      │  │    │      │    │       │  │     │ │    │    │      │    │   │
 55%  │  └────┘      └────┘       └──└─────┘─┘    └────┘      └────┘   │
      │  정도전      정약용             왕          장영실      이순신    │  ← 이름 라벨
      │   ↑             ↑                             ↑           ↑     │
 65%  │ [도제클러스터] [도제클러스터]              [도제클러스터] [도제클러스터] │
      │  📋🖋️📜         🎓🎨                         🎨⚙️🏗️📡      🔍💊🧪  │  ← 도제 40px, 매니저 발밑 오프셋
      │                                                                  │
 75%  │                                                                  │
      │                                                                  │
      0%               25%           50%          75%              100%
```

### 도제 등장 동선

```
  좌 가장자리 (x:-60px)                      우 가장자리 (x:화면폭+60px)
       │                                               │
       │  슬라이드 인 →                 ← 슬라이드 인  │
       │                                               │
       │  정도전 발밑 착지 (20%, 65%)   장영실 발밑 착지 (70%, 65%)
       │  정약용 발밑 착지 (30%, 65%)   이순신 발밑 착지 (80%, 65%)
       │                                               │
       │  ← 슬라이드 아웃              슬라이드 아웃 → │
```

---

## 2. 영역별 설명

### 2.1 헤더 — 단청 오방색 (그대로 유지, h-12 = 48px)

현행 구현 그대로 가져감. 오방색 5등분 + 중앙 타이틀 + 우측 SSE 연결 indicator.
변경 없음.

### 2.2 어전 영역 (메인, flex-1)

화면 전체에서 가장 비중이 큰 구역. 배경·왕·매니저 4인·도제 등장 영역이 모두 이 안에 들어감.

#### 일월오봉도 배경 SVG 명세

```
SVG 크기: 어전 영역 width × height (100% × 100%, position: absolute, z-index: 0)

요소 목록:
  1. 배경 그라디언트
     - 상단 1/3: #1A2B47 (진남·밤하늘)  → #3B5E8C (낮 하늘)
     - 하단 2/3: #2D5A27 (산 초록)
     - linearGradient id="sky-bg", x1=0 y1=0 x2=0 y2=1

  2. 달 (좌측 상단 20%, 15%)
     - circle r=32px, fill=#F5E6A3 (달빛 노랑)
     - 외곽 glow: filter blur(8px) 동일 색 반투명 원

  3. 해 (우측 상단 80%, 15%)
     - circle r=32px, fill=#E87C2A (붉은 해)
     - 외곽 glow 동일

  4. 5봉 실루엣 (하단 중앙 집중)
     - polygon 5개: 삼각형 크기 순 (가운데 가장 큼)
     - fill=#1A2B1A (진녹 실루엣)
     - 배치: x 15%, 28%, 50%, 72%, 85% / y 하단 30~60% 범위
     - 봉우리 높이: 55px, 70px, 90px, 70px, 55px (중앙 대칭)

  5. 옥좌 플랫폼 (중앙 하단, x=50%, y=52%)
     - rect 120×24px, fill=#8B5C1E (단청 나무 갈색)
     - 상단 border-radius 4px, 좌우 계단 효과 (rect×2 추가)

z-index: 0 (캐릭터들은 z-index: 10~20 위에 올라감)
```

#### 왕 캐릭터 — KingCharacter (신규 컴포넌트)

```
위치: 어전 영역 내 position: absolute
  - left: 50%, transform: translateX(-50%)
  - top: 35%

크기: 80×80px (픽셀 아트 스프라이트 영역)
  - 매니저(64px)보다 한 단계 큼 — 시각 위계 명확

픽셀 아트 구성 (16-bit 2D):
  - 곤룡포 자황 #C9A227 (왕복)
  - 익선관 (왕관) — 두 갈래 가지 위로 올라감
  - 옥색 도포 안에 자황 겉옷
  - 3등신 SD 비례 (머리 1 : 몸 2)

말풍선:
  - position: absolute, bottom: 100% + 8px (캐릭터 머리 바로 위)
  - 꼬리: 아래 방향 중앙 (▼)
  - 테두리: #C9A227 (자황), 배경: var(--bg-hanji)
  - 가시 조건: 왕이 task_start 또는 task_end 이벤트 수신 시 2초 표시 후 fadeOut

옥좌:
  - KingCharacter 발밑에 옥좌 플랫폼 SVG가 렌더됨 (배경 SVG의 일부)
```

#### 매니저 4인 배치 — ManagerCharacter 변경

```
현행: grid-cols-4, 균등 4분할 (좌→우 정도전·장영실·이순신·정약용)
변경: position: absolute, 어전 영역 안에서 좌우 비대칭 배치

문관 좌측 (position: absolute):
  정도전 📐  →  left: 18%,  top: 40%
  정약용 💡  →  left: 30%,  top: 45%   (왕보다 약간 앞쪽·낮은 느낌)

무관 우측 (position: absolute):
  장영실 🔧  →  right: 30%, top: 45%  (= left: 70%)
  이순신 ⚓  →  right: 18%, top: 40%  (= left: 82%)

왕:
  중앙          left: 50%,  top: 35%   (문관·무관보다 한 단계 위)

크기: 매니저 64×64px (픽셀 아트), 왕 80×80px

props 추가:
  side: "left" | "right" | "center"
  → 말풍선 꼬리 방향 결정 (좌 캐릭터 = 꼬리 우측 하단, 우 캐릭터 = 꼬리 좌측 하단)
```

#### 말풍선 위치 변경 — ChatBubble 이동

```
현행: 화면 하단 별도 h-48 섹션에 목록형 렌더

변경: 각 캐릭터 컴포넌트 내부 position: absolute
  - bottom: 100% + 8px (캐릭터 머리 위)
  - 정도전: right: 0  (말풍선이 오른쪽으로 펼쳐짐 — 왕 방향)
  - 정약용: right: 0
  - 장영실: left: 0   (말풍선이 왼쪽으로 펼쳐짐 — 왕 방향)
  - 이순신: left: 0
  - 왕:     left: 50%, transform: translateX(-50%)  (가운데)

말풍선 꼬리 방향:
  - 좌 문관 (정도전·정약용): 꼬리 우측 하단 (▶ 모양, 왕 방향)
  - 우 무관 (장영실·이순신): 꼬리 좌측 하단 (◀ 모양, 왕 방향)
  - 왕: 꼬리 아래 중앙 (▼)

표시 조건:
  - agent_start / agent_message / agent_end 이벤트 발생 시 해당 캐릭터 위 말풍선 표시
  - 3초 후 fadeOut (Framer Motion AnimatePresence)
  - 동시에 여러 캐릭터 말풍선 가능 (z-index 별도 관리)

하단 채팅 로그 섹션:
  - 제거 (h-48 섹션 삭제)
  - 대신 어전 영역 좌측 하단 또는 별도 collapsed 패널로 이전 고려 (β++ 후속 확정)
```

#### 도제 등장 영역

```
도제 등장 동선:
  - 초기 위치: 좌측 도제 → x: -60px (화면 왼쪽 바깥), y: 해당 매니저 y + 36px
              우측 도제 → x: 화면폭 + 60px (화면 오른쪽 바깥)

  - 등장 (agent_start 이벤트):
    Framer Motion animate: { x: 목표좌표 }
    duration: 0.4s, ease: "easeOut"
    목표 위치: 매니저 발밑 오프셋 (현행 getDojeOffsets 로직 유지)

  - 대기: idle 미세 흔들기 (현행 유지)

  - 퇴장 (agent_end 이벤트):
    animate: { x: 초기 위치 (바깥) }
    duration: 0.3s, ease: "easeIn"

  도제 크기: 40×40px (픽셀 아트, β++ 후속에서 개별 스프라이트)
  현재는 색 원 + emoji placeholder 유지
```

### 2.3 두루마리 (TaskScroll) — 위치·크기

```
위치: 헤더 바로 아래 (고정, shrink-0)
크기: h-16 (64px), width: 100%
스타일: 현행 그대로 유지 (한지 베이지 + 명조체 + 진행도 블록)
변경 없음.
```

### 2.4 KingInput — 위치·크기

```
위치: 화면 최하단 (고정, shrink-0)
크기: h-14 (56px), width: 100%

현행 변경 없음 (disabled placeholder 유지).
β++ 시점에서도 입력 기능 활성화는 스코프 아웃.
```

### 2.5 SSE 연결 indicator — 위치

```
현행: 헤더 우측 끝 (● 실시간 / ● 끊김)
변경 없음. 헤더 오방색 오버레이 안에 유지.
```

---

## 3. 컴포넌트 신규·변경 표

| 컴포넌트 | 신규/변경 | 명세 요점 |
|---|---|---|
| `KingCharacter.tsx` | **신규** | 80×80px 픽셀 왕. props: `message?: string`, `isActive?: boolean`. 말풍선 absolute 내장. 옥좌는 배경 SVG로 분리. |
| `IlwolObongdo.tsx` | **신규 SVG** | 어전 영역 전체 배경. position: absolute, z-index:0. 달·해·5봉·옥좌 플랫폼. 순수 SVG, 이미지 파일 X. |
| `ManagerCharacter.tsx` | **변경** | `side: "left" \| "right"` props 추가. 말풍선 absolute 내장. 하단 채팅 섹션 연결 제거. position absolute 좌표 수신 (부모 page.tsx에서 style prop으로 전달). |
| `ChatBubble.tsx` | **변경** | 독립 컴포넌트 유지하되 사용 위치 이동. ManagerCharacter / KingCharacter 내부에서 렌더. `side` prop 추가 (`"left" \| "right" \| "center"`). 꼬리 방향 side에 따라 조건부. |
| `page.tsx` 어전 구획 | **변경** | 기존 `grid grid-cols-4` → `relative` 컨테이너 + absolute 자식들. KingCharacter 추가. IlwolObongdo 배경 추가. 하단 말풍선 섹션(`h-48`) 삭제. |
| `DojeCharacter.tsx` | 변경 최소 | 등장·퇴장 x축 슬라이드 애니 추가 (Framer Motion). 현행 y축 발밑 배치 로직 유지. |
| `TaskScroll.tsx` | 변경 없음 | — |
| `KingInput.tsx` | 변경 없음 | — |

---

## 4. 반응형·접근성

### 모바일 (세로 9:16, 인스타 reels 대상)

```
브레이크포인트: max-width 640px

어전 영역:
  - 왕 위치: 중앙 유지 (top: 30%)
  - 매니저 4인: position absolute → 왕 주변 4방향으로 재배치
    정도전: left: 10%, top: 38%   (화면 폭이 좁아 겹침 허용)
    정약용: left: 22%, top: 48%
    장영실: right: 22%, top: 48%  (= left: 78%)
    이순신: right: 10%, top: 38%
  - 도제 클러스터: 매니저 발밑 오프셋 ±24px로 축소 (현행 ±36px → ±24px)
  - 말풍선 최대 너비: min(200px, 50vw)

일월오봉도:
  - 달·해 크기 24px로 축소
  - 5봉 높이 40/55/70/55/40px로 축소

헤더:
  - 타이틀 텍스트 크기 text-sm → text-xs

KingInput:
  - 높이 h-12로 축소 가능 (입력창 placeholder 유지)
```

### 접근성

```
aria-label:
  - 어전 영역 section: aria-label="어전 도열 — 매니저 4인과 임금"
  - KingCharacter: aria-label="임금 {isActive ? '작업 중' : '대기 중'}"
  - ManagerCharacter: 현행 그대로 유지 (aria-label 있음)
  - IlwolObongdo: aria-hidden="true" (장식 요소)

키보드 네비:
  - 캐릭터는 시각 전용. 포커스 없음 (tabIndex=-1)
  - KingInput (disabled): aria-disabled="true" 현행 유지
  - 새 어전 영역 내 포커스 트랩 없음

role="log":
  - 하단 채팅 섹션 제거 시 대안:
    어전 영역에 aria-live="polite" 숨김 span 두어 말풍선 메시지를 스크린 리더에 전달
    예: <span className="sr-only" aria-live="polite">{latestBubble}</span>

색대비:
  - 말풍선 배경 var(--bg-hanji) #F4ECD8 + 텍스트 #2A2A2A → 대비 14:1 OK
  - 이름 라벨 각 캐릭터 hex → 한지 베이지 배경 기준 확인 필요
    (이순신 #1A2B47은 배경 대비 OK, 정약용 #7BA05B는 경계선, bold 처리 권장)
```

---

## 5. 색상·타이포 토큰

### 색상 토큰

```css
/* 한지 베이지 계열 */
--bg-hanji:        #F4ECD8   /* 기본 배경 — 현행 유지 */
--bg-hanji-dark:   #EDE0C4   /* KingInput 배경 — 현행 유지 */
--bg-hanji-shadow: #D9C9A8   /* 구분선·테두리 — 현행 유지 */

/* 단청 오방색 — 현행 유지 */
--dancheong-blue:  #2C5F8D   /* 청 */
--dancheong-red:   #D94F2B   /* 적 */
--dancheong-yellow:#C9A84C   /* 황 */
--dancheong-white: #E8DCC8   /* 백 */
--dancheong-black: #2D2926   /* 흑 */

/* 캐릭터 hex — 기관도제께 픽셀 자산 제작 시 전달 */
--king-gold:       #C9A227   /* 곤룡포 자황 */
--dojeon-blue:     #2C5F8D   /* 정도전 청람 */
--yeongsil-brown:  #B8651E   /* 장영실 적동 */
--sunsin-navy:     #1A2B47   /* 이순신 먹/진남 */
--yagyong-green:   #7BA05B   /* 정약용 녹두 */
--vermilion:       #C0392B   /* 반려 주칠 */

/* 일월오봉도 배경 전용 */
--ilwol-sky-top:   #1A2B47   /* 밤 하늘 */
--ilwol-sky-mid:   #3B5E8C   /* 낮 하늘 */
--ilwol-mountain:  #1A2B1A   /* 봉우리 실루엣 */
--ilwol-moon:      #F5E6A3   /* 달빛 */
--ilwol-sun:       #E87C2A   /* 붉은 해 */
--ilwol-throne:    #8B5C1E   /* 옥좌 나무 */
```

### 타이포 토큰 (현행 유지)

```
본문 한글: Pretendard (또는 Spoqa Han Sans, OFL 라이선스)
강조·제목: Noto Serif KR (--font-serif CSS 변수)
숫자·코드: JetBrains Mono
```

---

## 6. 정도전께 단계 분해 입력

### M3.5 — 어전 도열 레이아웃 단계 후보

```
M3.5-a (0.5일)  page.tsx 어전 구획 재구성
  - grid → relative + absolute 전환
  - 매니저 4인 좌표 props 지정 (side="left"|"right")
  - KingCharacter placeholder (80px 원 + 🤴 emoji) 추가

M3.5-b (0.5일)  ChatBubble 위치 이전
  - h-48 하단 섹션 제거
  - ManagerCharacter 내부 ChatBubble absolute 내장
  - KingCharacter에 ChatBubble absolute 내장
  - side prop에 따른 꼬리 방향 분기

M3.5-c (0.5일)  IlwolObongdo 배경 SVG
  - 그라디언트 하늘 + 달·해 원 + 5봉 실루엣 + 옥좌 플랫폼
  - position absolute, z-index 0
  - aria-hidden="true"

M3.5-d (0.5일)  통합 확인 + 모바일 반응형
  - 640px 브레이크포인트 매니저 재배치
  - aria-live sr-only span 추가
  - 스크린 확인 (npm run dev 런타임 점검)
```

### M3.7 — 픽셀 자산 단계 후보 (기관도제·단청도제 협업)

```
M3.7-a (1일)  왕 픽셀 스프라이트 SVG
  - 80×80px 그리드, 4px 단위 픽셀 블록
  - 곤룡포 자황 #C9A227 + 익선관 + 3등신 SD 비례
  - idle 프레임 1장 (β++에서는 정적 단일 프레임)

M3.7-b (1일)  매니저 4인 픽셀 스프라이트 SVG
  - 64×64px 그리드
  - 정도전: 관복 청람 #2C5F8D + 조선 유관 📐
  - 장영실: 공인 복색 적동 #B8651E + 도구 🔧
  - 이순신: 갑옷 먹/진남 #1A2B47 + 투구 ⚓
  - 정약용: 실학자 녹두 #7BA05B + 거중기 도구 💡
  - 각 1장 정적 프레임 (idle 애니는 Framer Motion y축 흔들기로 충당)

M3.7-c (0.5일)  public/characters/ 교체 + CharacterAvatar 연결
  - 기존 placeholder SVG → 픽셀 스프라이트 SVG swap
  - CharacterAvatar.tsx에서 /characters/{agentName}.svg 로드
```

---

### 다음 차례

이 그림을 정도전 대감께 올려 M3.5·M3.7 단계를 확정하시고, 단청도제(frontend-dancheong)·기관도제(backend-gigwan)께 구현을 청하소서. 픽셀 자산은 기관도제와 단청도제가 협업하되, 색상 토큰(§5)을 이 문서에서 그대로 가져가면 됩니다.
