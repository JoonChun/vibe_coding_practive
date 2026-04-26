# ☕ News Brew

> 키워드 기반 AI 뉴스 큐레이션 자동 비서

사용자가 등록한 키워드의 뉴스를 자동 수집해 AI가 중요도·요약을 처리하고, 결과를 이메일과 Google Sheets로 전달하는 로컬 실행형 웹 애플리케이션입니다.

## 🎯 사용자 시나리오

매일 아침 출근길에 AI가 정리한 산업 트렌드 리포트를 메일로 받고, 과거 기록은 웹 UI에서 날짜별로 다시 조회합니다. 정보 과잉 시대에 뉴스 확인 시간을 단축하고 중요한 정보를 체계적으로 아카이빙하는 것이 목적입니다.

## ✨ 주요 기능

| 기능 | 설명 |
| --- | --- |
| **키워드 & 필터링 관리** | 키워드 추가/삭제, 제외 단어, 도메인 블랙리스트, AI 광고성 필터 프롬프트 |
| **뉴스 수집 엔진** | SerpAPI 또는 Naver 검색 API, 수집 기간 / 수량 / 정렬 기준 제어 |
| **AI 브루잉** | OpenAI GPT-4o-mini 또는 Gemini로 중요도 1~10점 판별 + 개조식 3~5줄 요약 |
| **이메일 자동 발송** | Resend API + 커피 브라운 톤 HTML 템플릿, 발송 실패 시 3회 재시도 |
| **Google Sheets 아카이빙** | 서비스 계정 기반 시트 자동 기록 (제목·링크·날짜 백업) |
| **자동 스케줄러** | APScheduler 기반 매일 지정 시간(HH:MM) 자동 실행 |
| **실시간 대시보드** | WebSocket으로 단계별 진행 로그 출력, 즉시 실행 버튼 |
| **아카이브** | 날짜·키워드별 과거 요약본 검색 및 원문 링크 |
| **다국어 UI** | 한국어 / 영어 토글 |
| **도움말 페이지** | `/help`에서 시작 가이드, 기능 카드, FAQ 제공 |

## 🛠 기술 스택

| 구분 | 스택 |
| --- | --- |
| **Frontend** | React 18 + Vite + TypeScript, Tailwind CSS, React Router |
| **Backend** | Python 3.10+, FastAPI, APScheduler, WebSockets |
| **Database** | SQLite (`aiosqlite`) — 설정·아카이브 저장 |
| **외부 API** | SerpAPI / Naver, OpenAI / Gemini, Resend, Google Sheets |

## 🚀 시작하기

### 1) 백엔드

```bash
cd newsBrew/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # 키 입력
uvicorn main:app --reload  # http://localhost:8000
```

### 2) 프론트엔드

```bash
cd newsBrew/frontend
npm install
npm run dev                # http://localhost:5173
```

### 3) 첫 사용 흐름

1. `/settings`에서 API 키, 수신 이메일, 자동 실행 시간 입력
2. `/keywords`에서 추적할 키워드 추가
3. 대시보드의 **지금 브루잉 시작** 클릭으로 즉시 실행 또는 스케줄 대기
4. `/archive`에서 과거 결과 검색·재열람

자세한 가이드는 앱 안의 **도움말** 페이지(`/help`)를 참고하세요.

## 🔑 환경 변수 (`backend/.env`)

```env
# 뉴스 수집
SERPAPI_KEY=...
# 또는 Naver
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...

# AI
OPENAI_API_KEY=...
# 또는
GEMINI_API_KEY=...

# 이메일
RESEND_API_KEY=...

# Google Sheets (옵션)
GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service_account.json
GOOGLE_SHEET_ID=...

# 앱
DATABASE_URL=sqlite+aiosqlite:///./newsbrew.db
```

> 🔒 `.env`, `service_account.json`, SQLite DB 파일은 `.gitignore`로 보호됩니다. 커밋 전 항상 확인하세요.

## 📁 프로젝트 구조

```text
newsBrew/
├── backend/
│   ├── main.py             # FastAPI 엔트리
│   ├── routers/            # keywords / settings / archives / brew
│   ├── services/           # news_collector, ai_brewer, email_sender, sheets, brew_orchestrator
│   ├── database/           # SQLAlchemy async 모델·세션
│   ├── ws/                 # WebSocket 매니저
│   ├── tests/              # pytest
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/          # Dashboard, Keywords, Archive, Settings, Help
│       ├── layouts/        # 사이드바·모바일 네비
│       ├── contexts/       # Language, Brew, Toast
│       ├── locales/        # ko/en 번역
│       └── api/
├── design/                 # 디자인 레퍼런스 HTML/PNG
├── docs/                   # 추가 문서
└── prd.md                  # 제품 요구사항 정의서
```

## 🧪 테스트

```bash
cd newsBrew/backend
PYTHONPATH=. pytest -v
```

## 🎨 디자인 컨셉

- **테마**: Warm & Minimal — 따뜻한 에스프레소 바 감성
- **컬러**: Brew Coffee `#4B3621`, Warm Cream `#F5F5DC`, Morning Orange `#FF8C00`
- **타이포**: 헤드라인은 이탤릭, 본문은 가독성 중심

## 📄 추가 문서

- [PRD (제품 요구사항 정의서)](./prd.md)
- [FE/BE 병렬 작업 계획](./FE_BE_parallel_plan.md)

---
*Brewed with ❤️ by Antigravity (vi.joon)*
