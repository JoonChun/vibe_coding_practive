# 🌙 vibe_ws

AI와 감성(Vibe)으로 구축하는 개인 프로젝트 아카이브입니다. 바이브 코딩을 통해 만든 결과물들과 학습 기록을 통합 관리합니다.

## 📂 프로젝트 목록

### 1. [FocusBear](./focusBear) 🐻
- **슬로건**: 당신의 몰입이 그려내는 따뜻한 기록, '몰입의 지도'
- **핵심 기능**: 집중 타이머(스톱워치/뽀모도로), 히트맵 캘린더, 통계 대시보드, 카테고리 관리
- **기술 스택**: React, TypeScript, Vite, Dexie.js (IndexedDB), Tailwind CSS, Framer Motion, PWA

### 2. [All-in-One Life Calculator](./all-in-one_calculator) 🧮
- **슬로건**: 현대인의 복잡한 일상 속 다양한 수치를 직관적으로 계산
- **핵심 기능**: 복리/적금, 대출 상환, 연봉 실수령액, 단위 변환, D-Day, 비교 리포트
- **기술 스택**: Next.js 14, TypeScript, Tailwind CSS, Recharts, PWA

### 3. [multiProfile](./multiProfile) 🔗
- **슬로건**: AI를 활용한 개인용 멀티 링크 페이지 (성장형 포트폴리오)
- **핵심 기능**: 프로젝트 아카이브 보드, AI 챗봇(Gemini), 로컬 관리자 패널
- **기술 스택**: HTML, CSS, JavaScript, Tailwind CSS

### 4. [MAPF Post-Mortem Analyzer](./MAPF-Post-Mortem-Analyzer) 🤖
- **슬로건**: 다중 에이전트 경로 탐색(MAPF) 데드락 사후 분석 샌드박스
- **핵심 기능**: 50MB 로그 파서, Wait-for-Graph 자동 추출, 브라우저 내 A* Re-plan, 운동학적 충돌 검증
- **기술 스택**: React + Vite, TypeScript, Zustand, Canvas/SVG, Web Workers, Gemini API(서버리스 BFF)

### 5. [News Brew](./newsBrew) ☕
- **슬로건**: 키워드 기반 AI 뉴스 큐레이션 자동 비서
- **핵심 기능**: 키워드 수집, AI 중요도 판별·요약, 이메일 발송, Google Sheets 아카이빙, 자동 스케줄러
- **기술 스택**: React + Vite, TypeScript, Tailwind CSS · FastAPI, APScheduler, SQLite, WebSocket · OpenAI / Gemini, Resend, SerpAPI

### 6. [ReviewPick AI](./reviewPickAI) 🛒
- **슬로건**: 쿠팡·네이버 쇼핑 리뷰를 AI로 한 번에 분석하는 크롬 익스텐션
- **핵심 기능**: 자동 리뷰 크롤링, Gemini 감성 분석, D3 키워드 마인드맵, 비교 분석, PDF/CSV/PNG 내보내기
- **기술 스택**: React + Vite (Manifest V3), TypeScript, Tailwind CSS, D3.js, Chart.js, Gemini API

### 7. [PharmaTA Insight](./pharmaTA) 💊
- **슬로건**: AI 기반 질환군(TA)별 제약·바이오 데이터 인사이트 플랫폼
- **상태**: 기획 단계 (PRD 정의 완료, 구현 예정)
- **기술 스택(예정)**: Next.js (App Router), FastAPI, PostgreSQL + pgvector / Supabase, Gemini 1.5

## 🚀 시작하기

각 프로젝트 폴더의 `README.md`를 참고하세요. 대부분의 React/Next 프로젝트는 다음 패턴으로 동작합니다.

```bash
cd <project-folder>
npm install
npm run dev
```

`newsBrew`처럼 백엔드가 분리된 프로젝트는 `backend/`와 `frontend/` 각각의 README를 참고하세요.

## 🌿 브랜치 전략

```
main ← develop ← feat/*
```

- `feat/*` : 기능 개발
- `develop` : 통합 검수
- `main` : 배포

---
*Created with ❤️ by Antigravity (vi.joon)*
