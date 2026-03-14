💜 PRD: vi.joon Link
AI와 감성(Vibe)으로 구축하는 개인 프로젝트 아카이브

1. 프로젝트 개요
프로젝트 명: vi.joon Link

핵심 컨셉: '바이브 코딩(Claude + Antigravity)'을 통해 만든 결과물들을 기록하고 일반인에게 그 가능성을 전달하는 성장형 포트폴리오.

목적: * 바이브 코딩 입문 가이드 정독 유도.

인스타그램 팔로워 증대 및 퍼스널 브랜딩 강화.

타겟: AI 활용법에 관심이 있는 일반인 및 예비 창작자.

1. 사용자 시나리오
유입: SNS(인스타그램 등)를 통해 프로필 링크 클릭.

탐색: 미니멀한 UI와 보라색 톤의 디자인에 호감을 느끼며 프로젝트 결과물 확인.

전환: "0원으로 시작하는 AI 앱 개발"과 같은 매력적인 문구에 이끌려 '바이브 코딩 가이드' 클릭.

확정: 가이드 정독 후 제작자(vi.joon)에 대한 신뢰를 바탕으로 인스타그램 팔로우.

1. 핵심 기능 목록
하이라이트 CTA 영역: 최상단에 배치된 가이드 유입용 대형 버튼.

프로젝트 아카이브 보드: 데이터 기반으로 생성되는 프로젝트 카드 리스트.

소셜 연결: 인스타그램 팔로우 버튼 및 링크 연동.

로컬 관리자 패널 (Hidden): * 드래그 앤 드롭을 통한 링크 순서 변경.

프로필 사진 및 텍스트 실시간 수정 (Preview).

수정된 데이터를 JSON 파일로 다운로드하거나 텍스트로 복사하는 기능.

1. 기술 스택
Frontend: HTML5, CSS3, Vanilla JavaScript

Styling: Tailwind CSS (via CDN)

Data: LocalStorage & JSON (config.js)

Hosting: GitHub Pages

Tools: Claude 3.5 Sonnet, Antigravity

1. 화면 구성 (Layout)
Header: 프로필 이미지(보라색 테두리) + 타이틀(vi.joon Link) + 소개 문구.

Featured Area: 강조된 '바이브 코딩 가이드' 버튼.

Project Grid: 프로젝트 카드 (썸네일, 제목, 설명, 사용 툴 태그).

Footer: 소셜 아이콘 및 저작권 정보.

Admin Panel (Overlay): Ctrl + M 입력 시 나타나는 데이터 수정 및 저장 패널.

1. 상세 기능 명세
동적 렌더링: data.js의 JSON 데이터를 기반으로 JS가 HTML 요소를 자동 생성.

정렬 기능: Sortable.js 등을 활용하거나 Native API로 구현된 카드 순서 변경.

데이터 익스포트: * File Save: 수정한 설정을 config.json으로 내려받기.

Text Copy: 수정된 JSON 코드를 즉시 복사하여 소스 코드에 붙여넣기 지원.

1. 디자인 가이드
Main Color: #8A2BE2 (Electric Purple)

Background: #0F1014 (Dark Charcoal)

Point: Glassmorphism(유리 효과) 및 Neon Glow(네온 효과).

Font: Pretendard (가독성 높은 Sans-serif).

Mood: 미니멀, 트렌디, 테크니컬.

1. 제약 사항
No-Backend: 서버 없이 동작하며, 데이터 영구 저장은 소스 코드 수정을 통해 수행.

Mobile-First: 인스타그램 인앱 브라우저 최적화(Safe Zone 확보).

Minimal Library: 외부 라이브러리 사용을 최소화하여 Claude가 유지보수하기 쉬운 구조 유지.
