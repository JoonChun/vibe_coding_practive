# 🐻 FocusBear (포커스베어)

> 당신의 몰입이 그려내는 따뜻한 기록, **'몰입의 지도'**

집중 시간을 기록하고 시각화하는 로컬 우선(Local-first) PWA입니다. 귀여운 곰 캐릭터와 매트릭스 테마로 몰입의 재미를 더합니다.

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **집중 타이머** | 스톱워치 / 뽀모도로 모드, 원클릭 시작·정지 |
| **몰입의 지도** | 날짜별 히트맵 캘린더, 집중 시간에 따른 색상 농도 변화 |
| **타임라인 메모** | 세션 종료 시 자동 타임스탬프 기반 메모 저장 |
| **통계 대시보드** | 주간 차트, 카테고리 파이, 시간대별 히트맵 |
| **수동 기록** | 타이머를 못 켰을 때 시간 범위로 직접 입력 |
| **카테고리 관리** | 설정에서 카테고리 추가·삭제, 10가지 프리셋 컬러 |
| **실행 취소/다시 실행** | 세션 변경사항 Undo/Redo 지원 |
| **데이터 관리** | JSON/CSV 내보내기 및 가져오기 |
| **PWA** | 오프라인 사용, 홈 화면 설치 지원 |
| **다크 모드** | 시스템 설정 연동 + 수동 토글 |

## 🛠 기술 스택

- **Framework**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS
- **Animation**: Framer Motion, HTML5 Canvas (Matrix Effect)
- **Storage**: IndexedDB via Dexie.js (로컬 영속성)
- **Charts**: Recharts
- **PWA**: Vite PWA Plugin (Workbox)

## 🚀 시작하기

```bash
cd focusBear
npm install
npm run dev
```

빌드:
```bash
npm run build
npm run preview
```

테스트:
```bash
npm test
```

## 📁 프로젝트 구조

```
focusBear/
├── src/
│   ├── components/
│   │   ├── dashboard/     # 타이머, 곰 캐릭터, 매트릭스
│   │   ├── calendar/      # 히트맵 캘린더, 수동 입력
│   │   ├── stats/         # 주간 차트, 카테고리 파이, 히트맵
│   │   ├── settings/      # 카테고리 관리, 데이터 내보내기
│   │   └── layout/        # 헤더, 사이드바, 레이아웃
│   ├── context/           # AppContext (전역 상태)
│   ├── db/                # Dexie 스키마, 세션·카테고리 CRUD
│   ├── hooks/             # useTimer, useUndoRedo, useTheme
│   ├── types/             # TypeScript 타입 정의
│   └── workers/           # 타이머 Web Worker
└── public/                # PWA 아이콘, favicon
```

## 💾 데이터 저장 방식

모든 데이터는 **브라우저 IndexedDB**에 로컬 저장됩니다. 서버 통신 없음.

> 브라우저 캐시 삭제 시 데이터 유실 위험 — 설정에서 정기적으로 JSON 백업을 권장합니다.

---
*Built with ❤️ by Antigravity (vi.joon)*

개발도감(devDogam)에서 라이브 통합 시험 대상으로 활용됨. (Phase 1 M2.4 시연)
