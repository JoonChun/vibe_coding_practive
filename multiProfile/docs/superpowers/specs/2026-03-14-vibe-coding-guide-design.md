# 바이브 코딩 가이드 페이지 설계

## 개요

vi.joon Link 포트폴리오의 "이제 시작하는 바이브 코딩 프로젝트" CTA 버튼에 연결될 멀티 페이지 가이드.
코딩 경험이 없는 일반인과 초보 개발자를 대상으로, AI 도구(Antigravity, Claude, Gemini)를 활용한 1인 개발 방법을 안내한다.

## 타겟

- 코딩 경험 없는 일반인 (AI로 무언가 만들 수 있다는 것에 흥미를 느낀 사람)
- 초보 개발자/학생 (AI 툴 활용 개발에 관심있는 사람)
- 유입 경로: 인스타그램 프로필 → vi.joon Link → 가이드

## 파일 구조

```
multiProfile/
├── index.html              (기존 포트폴리오 - featured link 수정)
├── guide/
│   ├── index.html           (가이드 메인 - 3단계 카드 네비게이션)
│   ├── step1.html           (Step 1: 툴 설치하기)
│   ├── step2.html           (Step 2: PRD 작성하기)
│   ├── step3.html           (Step 3: 첫 프로젝트 만들기)
│   └── guide.css            (가이드 전용 스타일)
```

## 디자인 원칙

- 기존 vi.joon Link와 동일한 다크 보라 테마 유지
- Tailwind CSS (CDN) + Pretendard 폰트 재사용
- 모바일 퍼스트 (인스타 인앱 브라우저 최적화)
- Glassmorphism / Neon Glow 효과 일관성 유지

## 페이지별 상세

### 가이드 메인 (`guide/index.html`)

- 영문 라벨: "VIBE CODING GUIDE" (작은 uppercase, letter-spacing)
- 타이틀 2줄: "이제 시작하는" + "바이브 코딩" (보라색 강조)
- 3단계 스텝 카드 리스트:
  - Step 1: 툴 설치하기 — Antigravity, Claude, Gemini 셋업
  - Step 2: PRD 작성하기 — Gemini로 기획서 만들기
  - Step 3: 첫 프로젝트 만들기 — 실전! Antigravity + Claude
- 카드 디자인: glass-panel 스타일, 번호 원형 배지, 화살표
- 하단: "← vi.joon 프로필로 돌아가기" 링크

### Step 상세 페이지 공통 구조

- 상단: 진행 표시 바 (Step 1/3, 2/3, 3/3)
- 본문: 섹션별 제목 + 설명 텍스트 + 스크린샷 placeholder 번갈아 배치
- 하단: "← 이전" / "다음 →" 네비게이션 버튼
- 뒤로가기: 가이드 메인으로 돌아가기 링크

### Step 1: 툴 설치하기

섹션:
1. Antigravity란? — 간단 소개 + 공식 사이트 링크
2. Antigravity 설치 — 다운로드 및 설치 과정 (스크린샷 placeholder)
3. Claude 계정 만들기 — claude.ai 가입 안내
4. Gemini API 키 발급 — Google AI Studio에서 키 발급 과정

### Step 2: PRD 작성하기

섹션:
1. PRD란? — 프로젝트 기획서의 역할과 중요성
2. Gemini로 PRD 작성하기 — 프롬프트 예시 제공
3. 좋은 PRD의 구조 — 프로젝트 개요, 기능 목록, 기술 스택, 디자인 가이드
4. 실전 예시 — vi.joon Link PRD를 예시로 보여주기

### Step 3: 첫 프로젝트 만들기

섹션:
1. Antigravity에서 프로젝트 시작하기 — 새 프로젝트 생성
2. Claude에게 PRD 전달하기 — PRD를 기반으로 코드 생성 요청
3. 결과물 확인 및 수정 — 생성된 코드 확인, 수정 요청 방법
4. 배포하기 — Vercel 등으로 무료 배포하는 방법

## 데이터 변경

`data.js`의 `featured.link`를 `"./guide/index.html"`로 변경.

## 기술 스택

- HTML5 + Tailwind CSS (CDN) — 빌드 불필요
- Vanilla JS (최소한) — 필요 시 인터랙션
- Pretendard 폰트 (CDN)
- 정적 페이지 — Vercel 배포 그대로 유지
