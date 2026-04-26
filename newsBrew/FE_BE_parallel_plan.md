# [Project Plan] News Brew - FE/BE 병렬 개발 계획서

본 문서는 `prd.md`와 `design` 리소스를 기반으로, 프론트엔드(Antigravity)와 백엔드(Claude Code)가 충돌 없이 효율적으로 병렬 작업하기 위한 상세 가이드 및 설계안입니다.

---

## 1. 디렉토리 구조 및 역할 분리

두 AI 에이전트 간 파일 수정 충돌(Conflict)을 원천 차단하기 위해, 최상위 구조를 완전히 분리합니다.

```text
newsBrew/
├── frontend/         # 👉 Antigravity (프론트엔드 전담 구역)
│   ├── package.json
│   ├── src/
│   │   ├── api/      # 백엔드 통신 및 Mock 파일
│   │   ├── components/ # 공통 UI 및 페이지별 컴포넌트
│   │   ├── pages/    # 대시보드, 키워드, 아카이브 등
│   │   └── ...
│   └── (Vite 기반 React 프로젝트 설정 파일들)
│
├── backend/          # 👉 Claude Code (백엔드 전담 구역)
│   ├── requirements.txt
│   ├── main.py       # FastAPI 진입점
│   ├── database/     # SQLite 모델 및 설정
│   ├── services/     # 뉴스 수집, AI 브루잉, 이메일 발송
│   ├── routers/      # API 및 WebSocket 라우터
│   └── (Python 기반 백엔드 설정 파일들)
│
├── prd.md            # 기획서 (Read-only)
└── frontend_backend_plan.md # 본 계획서 파일
```

---

## 2. 각 에이전트별 작업 목표 (Milestone)

### 👨‍💻 프론트엔드 파트 (Antigravity)
**기술 스택:** React (Vite), Tailwind CSS, Shadcn/UI, Lucide React
1. **스캐폴딩:** `frontend` 폴더에 Vite 환경 구성 및 필요 패키지 설치.
2. **디자인 이식:** `design/` 폴더 내의 HTML/CSS 레이아웃(Warm & Minimal, Brew Coffee 테마)을 React 컴포넌트로 변환.
3. **Mocking(가짜 데이터) 연동:** 백엔드 API가 완성되기 전에도 화면을 테스트할 수 있도록, Mock 데이터(예: 키워드 리스트, 아카이브 리스트)를 활용하여 상태 관리 완벽 구현.
4. **WebSocket 클라이언트:** 대시보드에 표시될 실시간 진행 상태 로그 콘솔 UI 구현 및 WS 연결 로직 준비.

### 🤖 백엔드 파트 (Claude Code)
**기술 스택:** Python (FastAPI), SQLite, APScheduler, WebSockets
1. **서버 초기화:** `backend` 폴더에 FastAPI, SQLite 연동 기본 골격 구축.
2. **데이터베이스 스키마:** 키워드, 아카이브, 설정값을 저장하는 SQLite 테이블 설계 및 구축.
3. **핵심 로직(Brewing) 개발:** 
   - Google Custom Search / SerpApi 연동
   - OpenAI/Gemini를 이용한 뉴스 요약(프롬프트 엔지니어링)
   - Resend 이메일 발송 및 Google Sheets 백업 로직
   - 스케줄러(APScheduler) 연동 및 수동 실행 로직
4. **API 및 WebSocket 개통:** 프론트엔드에서 요청할 API 서버 응답 체계 확립 및 진행 로그용 WebSocket 개발.

---

## 3. 핵심 API 인터페이스 명세 (사전 약속)

프론트엔드와 백엔드가 독립적으로 개발될 수 있도록, 통신 규격을 먼저 정의합니다.

### 🌐 REST API (기본 URL: `http://localhost:8000/api`)

| 기능 | Method | Endpoint | Request (Body) | Response (Success) |
|---|---|---|---|---|
| **키워드 목록 조회** | GET | `/keywords` | - | `[{id, word, exclude_words, created_at}, ...]` |
| **키워드 추가** | POST | `/keywords` | `{word, exclude_words}` | `{id, word, exclude_words}` |
| **키워드 삭제** | DELETE | `/keywords/{id}` | - | `{"status": "success"}` |
| **환경 설정 조회** | GET | `/settings` | - | `{schedule_time, apikeys, emails}` |
| **환경 설정 저장** | POST | `/settings` | `{schedule_time, ...}` | `{"status": "success"}` |
| **아카이브 목록** | GET | `/archives` | - | `[{date, summary_count}, ...]` |
| **수동 브루잉 시작** | POST | `/brew/start` | - | `{"status": "started"}` |

### 🔌 WebSocket 통신 (기본 URL: `ws://localhost:8000/ws/logs`)
- **목적:** 백엔드의 뉴스 수집 및 요약 진행 상황을 실시간 대시보드 콘솔에 출력.
- **Message Format:** JSON 형식.
  ```json
  {
    "timestamp": "2026-04-19T10:00:00Z",
    "level": "INFO", 
    "message": "구글 검색 API에서 15건의 뉴스를 불러왔습니다."
  }
  ```

---

## 4. 백엔드(Claude Code)를 위한 특별 지시사항
이 문서를 읽고 있는 Claude Code에게 요청합니다:
1. `backend` 폴더를 생성하고 안에서만 작업해주세요. 프론트엔드 파일엔 일절 관여하지 마세요.
2. 개발 시작 전 로컬에 `SQLite` DB가 생성되도록 코드를 작성해주세요.
3. `main.py`에 CORS 설정(`allow_origins=["http://localhost:5173"]`)을 추가해 프론트와 통신이 되도록 하세요.
4. 비즈니스 로직(검색, 요약, 이메일) 구현에 집중하고 프론트 개발 진행과 상관없이 Postman이나 FastAPI Docs(`http://localhost:8000/docs`)에서 단위 테스트 가능하게 만들어주세요.

## 5. 실행 및 병합 계획 전략
- **로컬 구동:** 
  - 터미널 1: `cd frontend && npm run dev` (프론트 서버 :5173)
  - 터미널 2: `cd backend && uvicorn main:app --reload` (백엔드 서버 :8000)
- 프론트엔드는 개발 시 Proxy 설정을 통해 `/api` 요청을 `http://localhost:8000`으로 바이패스하도록 설정할 예정입니다.
