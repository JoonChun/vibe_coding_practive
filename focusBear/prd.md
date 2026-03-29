🐻 FocusBear(포커스베어) 프로젝트 PRD

1. 프로젝트 개요 (Project Overview)
프로젝트 명: FocusBear (포커스베어)

슬로건: 당신의 몰입이 그려내는 따뜻한 기록, '몰입의 지도'

배경: * 기존 업무용 툴의 딱딱함에서 벗어나 개인의 순수한 성취감을 위한 감성적 도구 필요.

데이터 유출 방지 및 오프라인 사용을 위한 '로컬 우선(Local-first)' 환경 지향.

주요 목표: * 단순한 시간 기록을 넘어 캘린더와 통계를 통한 '몰입 시각화' 제공.

귀여운 캐릭터와 매트릭스 테마를 통한 몰입의 재미 극대화.

1. 사용자 시나리오 (User Scenario)
Scenario A (몰입): 사용자가 카테고리를 정하고 타이머를 누르면, 곰 캐릭터가 안경을 쓰고 매트릭스 화면 앞에서 코딩을 시작함.

Scenario B (기록): 몰입이 끝나면 자동으로 타임스탬프가 찍힌 메모창이 뜨고, 사용자는 짧은 회고를 남김.

Scenario C (감상): 캘린더에 찍힌 곰 발바닥 아이콘과 히트맵을 보며 한 주간의 성취감을 느낌.

Scenario D (보정): 깜빡하고 타이머를 못 켰을 때, 수동으로 입력하면 기존 기록들이 새 기록에 맞춰 자동으로 쪼개지며 정리됨.

1. 핵심 기능 목록 (Core Features)
집중 타이머: 원클릭 시작/종료, 스톱워치 및 뽀모도로 모드 지원.

몰입의 지도 (Calendar): 집중 시간에 따른 색상 농도 변화(히트맵) 및 곰 발바닥 마킹.

타임라인 메모: 일별 자동 타임스탬프(HH:mm:ss) 기반 메모 기록.

통계 대시보드: 주간/월간 몰입 차트, 카테고리 비중 분석, 몰입 시간대 분석.

PWA(Progressive Web App): 오프라인 사용 가능, 데스크톱/모바일 홈 화면 설치 지원.

시스템 설정: 다크 모드(상단 토글), 데이터 JSON/CSV 내보내기 및 복구, 애니메이션 ON/OFF.

1. 기술 스택 (Technology Stack)
Framework: React (Vite)

Styling: Tailwind CSS

Animation: Framer Motion (UI), HTML5 Canvas API (Matrix Effect)

Storage: IndexedDB (Dexie.js) - 로컬 데이터 영속성 확보

Charts: Recharts

PWA: Vite PWA Plugin

Icons: Lucide React

1. 화면 구성 (Screen Composition)
상단 헤더: 로고, 오늘 총 집중 시간 요약, Undo/Redo 버튼, 다크모드 스위치.

좌측 사이드바: 대시보드(타이머), 몰입의 지도(캘린더), 성장 통계, 설정.

메인 콘텐츠:

대시보드: 중앙 곰 캐릭터(매트릭스 애니메이션), 타이머 제어부.

캘린더: 월간 히트맵, 클릭 시 우측에서 일별 상세 메모 타임라인 슬라이드 등장.

통계: 성취도 분석 차트 리포트.

1. 상세 기능 명세 (Detailed Specifications)
6.1 스마트 시간 기록 조정 (Smart Overlap Handling)
수동 입력 시 기존 기록과 겹칠 경우 새로운 기록을 우선하여 기존 데이터를 자동 조정합니다.

Splitting: 기존 중 추가 시 → [09-10], [10-11], [11-12]로 3분할.

Trimming: 앞뒤가 겹칠 경우 기존 기록의 시작/종료 시점을 새 기록에 맞춰 깎아냄.

Overwriting: 새 기록이 기존 기록을 완전히 덮을 경우 기존 기록 삭제.

6.2 애니메이션 및 성능 최적화
Matrix Effect: 곰의 모니터 화면에 흐르는 초록 글자는 Canvas API로 구현하여 CPU 부하 최소화. 설정에서 OFF 가능.

Undo/Redo: 데이터 변경 시 스택을 관리하여 전역적으로 실행 취소 및 다시 실행 지원.

Background Timer: Web Worker와 Date.now() 차이값 계산 방식을 사용하여 브라우저 절전 모드에서도 오차 없는 시간 측정.

1. 디자인 가이드 (Design Guide)
Theme:

Light: Warm White (#FDFBF7), Bear Brown (#8B4513) - 포근한 느낌.

Dark: Midnight Blue (#0F172A), Matrix Green (#00FF41) - 테크니컬한 몰입감.

Typography: Pretendard (UI), JetBrains Mono (Timer/Matrix).

Bear State: * Focus: 안경 쓰고 코딩 중 (매트릭스 배경).

Rest: 꿀단지와 함께 휴식 중.

1. 제약 사항 (Constraints)
보안: PWA 작동을 위해 배포 시 HTTPS 환경 필수.

데이터 보존: 브라우저 캐시 삭제 시 데이터 유실 위험이 있으므로 정기적인 수동 백업 알림 노출.

호환성: 초기 버전은 Chromium 기반 브라우저(Chrome, Edge) 최적화 우선.
