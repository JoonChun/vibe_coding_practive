# MAPF Post-Mortem Analyzer

다중 에이전트 경로 탐색(MAPF) 시스템에서 발생하는 데드락(Deadlock)과 충돌 상황을 시각적으로 분석하고, 브라우저 내에서 직접 재탐색 샌드박스를 실행해볼 수 있는 사후 분석 도구입니다.

## 🚀 Key Features

### 1. 2D 시각화 및 타임라인 컨트롤

* **Canvas 기반 렌더링**: 수천 대의 로봇 이동 경로를 부드럽게 시각화합니다.
* **인터랙티브 타임라인**: 재생/일시정지, 배속 조절, 프레임 단위 스크러빙을 통해 특정 시점의 로그를 정밀 분석합니다.

### 2. 스마트 데드락 감지 (Wait-for-Graph)

* **Cycle Detection**: DFS 알고리즘을 사용하여 에이전트 간의 대기 권한 순환(Cycle)을 자동으로 감지합니다.
* **시각 오버레이**: 데드락이 발생한 로봇들 사이에 붉은 간선을 그려 문제의 핵심 원인을 즉각 파악합니다.

### 3. 브라우저 내 샌드박스 Re-planner

* **Web Worker A* 탐색**: 메인 스레드 중단 없이 데드락 탈출을 위한 대체 경로를 즉석에서 계산합니다.
* **운동학적 충돌 검증**: 다각형 충돌 감지 알고리즘(SAT)을 통해 재탐색된 경로의 안전성을 검증합니다.

### 4. AI 기반 동적 스키마 어댑터

* **Gemini API 연동**: 표준화되지 않은 다양한 로그 포맷이 들어와도 AI가 데이터를 분석하여 분석 도구에 맞는 규격으로 자동 변환해주는 어댑터 레이어를 생성합니다.

## 🛠 Tech Stack

* **Frontend**: React, TypeScript, Vite
* **Styling**: Tailwind CSS (v4)
* **State Management**: Zustand
* **Visualization**: HTML5 Canvas, React Flow (Wait-for-Graph)
* **Backend (BFF)**: Vercel Serverless Functions
* **AI**: Google Gemini Pro (via `@google/genai`)

## 📦 Getting Started

### Prerequisites

* Node.js 18.x 이상
* Google Gemini API Key (동적 스키마 변환 기능 사용 시)

### Installation

```bash
# 프로젝트 폴더로 이동
cd MAPF-Post-Mortem-Analyzer/mapf-analyzer

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

### Usage

1. 브라우저에서 `http://localhost:5173`에 접속합니다.
2. 분석하고자 하는 MAPF JSON 로그 파일(예: `sample_mapf_log.json`)을 화면 중앙의 드롭존에 드래그 앤 드롭합니다.
3. 타임라인을 조절하며 데드락 발생 지점과 에이전트 상태를 확인합니다.

---
**Developed by Antigravity (Advanced Agentic Coding AI)**
