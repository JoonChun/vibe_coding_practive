# 🧩 MAPF Post-Mortem Analyzer

> 데드락의 근본 원인을 10초 만에 시각적으로 찾아내는 무설치 사후 분석 샌드박스

다중 에이전트 경로 탐색(Multi-Agent Path Finding, MAPF) 환경에서 발생한 정체·데드락 로그를 브라우저 안에서 곧바로 시각화하고, 인과관계 분석과 즉시 Re-plan을 지원하는 도구입니다.

## 🎯 해결하려는 문제

- 수만 줄의 텍스트 로그(JSON/CSV)에 의존해 원인 로봇을 찾는 비효율
- 격자상 충돌은 없었으나 회전 반경 때문에 부딪히는 운동학적 케이스 진단 어려움
- 알고리즘적 인과관계(우선순위 꼬임 등)를 짚어주는 범용 툴 부재
- 보안이 중요한 현장에서 서버·DB 구축 부담

## ✨ 주요 기능

| 기능 | 설명 |
| --- | --- |
| **로컬 로그 파서** | 50MB 이하 JSON/CSV 로그를 브라우저 내에서 즉시 파싱 (필수 키 누락 시 에러) |
| **Wait-for-Graph 추출** | 정지 에이전트 간 점유·대기 관계로 방향성 그래프를 만들고 사이클을 빨간 외곽선으로 강조 |
| **2D 토폴로지 렌더러** | Canvas 기반 맵·에이전트 시각화, 타임라인 슬라이더 + 데드락 마커 |
| **샌드박스 Re-planner** | Web Worker 위에서 A*로 우회 경로 재탐색, 점선 오버레이로 미리보기 |
| **운동학적 충돌 검증** | 에이전트 폴리곤 교집합을 프레임 단위로 검사해 회전 시 충돌 순간 캡처 |
| **AI 동적 스키마 어댑터** | 처음 보는 JSON 포맷의 첫 50줄을 Gemini API로 보내 파서 코드를 동적 생성 |

## 🛠 기술 스택

| 구분 | 스택 |
| --- | --- |
| **프레임워크** | React 18 + Vite + TypeScript |
| **상태 관리** | Zustand |
| **렌더링** | HTML5 Canvas (맵·에이전트), React Flow / SVG (그래프 오버레이) |
| **연산** | Web Workers (A*, DFS 사이클 탐색, 폴리곤 교집합) |
| **AI** | Gemini API (Vercel Serverless Functions BFF 프록시) |
| **배포** | Vercel / GitHub Pages |

## 🚀 시작하기

```bash
cd MAPF-Post-Mortem-Analyzer/mapf-analyzer
npm install
npm run dev
```

빌드 / 미리보기:

```bash
npm run build
npm run preview
```

브라우저에서 [http://localhost:5173](http://localhost:5173) 접속 후 좌측 드롭존에 로그 파일을 드래그 앤 드롭하세요.

## 🧪 샘플 로그

레포 루트의 다음 파일들로 즉시 테스트할 수 있습니다.

- `sample_mapf_log.json` — 기본 시나리오
- `complex_mapf_log.json` — 정면 충돌 + 사이클 데드락
- `large_complex_log.json` — 대용량 부하 검증용

## 📁 프로젝트 구조

```text
MAPF-Post-Mortem-Analyzer/
├── mapf-analyzer/          # React + Vite 앱
│   ├── src/
│   │   ├── components/     # 캔버스, 타임라인, 인스펙터
│   │   ├── store/          # Zustand 전역 상태(프레임/선택)
│   │   ├── workers/        # A*, DFS 사이클 탐색
│   │   ├── hooks/          # 재생/단축키 훅
│   │   └── utils/          # 파서, 그래프 유틸
│   ├── api/                # Vercel Serverless (Gemini 프록시)
│   └── public/
├── *.json                  # 샘플 로그
└── prd.md                  # 제품 요구사항 정의서
```

## 🎨 디자인 가이드 (요약)

- **테마**: Dark Mode 전용 / Flat Design (Background `#18181B`)
- **시맨틱 컬러**: Deadlock `#EF4444`, Penalty `#F59E0B`, Success `#10B981`
- **타이포**: UI는 Pretendard/Inter, 좌표·데이터는 JetBrains Mono

## 📄 추가 문서

- [PRD (제품 요구사항 정의서)](./prd.md)

---
*Managed by vi.joon*
