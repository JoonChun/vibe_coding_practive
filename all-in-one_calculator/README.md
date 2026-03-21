# 🧮 All-in-One Life Calculator (올인원 라이프 계산기)

현대인의 복잡한 일상 속 다양한 수치를 직관적이고 시각적으로 계산해 주는 프리미엄 웹 어플리케이션입니다.

![All-in-one Calculator](https://raw.githubusercontent.com/JoonChun/vibe_ws/main/all-in-one_calculator/public/icons/icon-512.png)

## ✨ 주요 기능

### 1. 다양한 라이프 계산기
- **📈 복리/적금 계산기**: 원금과 적립액에 따른 자산 성장 추이를 시각화하고 전년 대비 증가율을 분석합니다.
- **🏦 대출 상환 계산기**: 원리금균등, 원금균등, 만기일시 상환 등 다양한 방식에 따른 상환 스케줄을 제공합니다.
- **💸 연봉 실수령액 계산기**: 비과세 항목과 공제 내역을 반영한 실제 월 수령액을 계산합니다.
- **📏 단위 변환기**: 길이, 넓이, 무게, 부피 등 다양한 단위를 실시간으로 변환합니다.
- **📅 디데이 계산기**: 중요한 일정까지 남은 시간을 관리합니다.

### 2. 스마트 기능
- **📊 비교 리포트**: 서로 다른 계산 결과(예: 서로 다른 대출 조건)를 최대 3개까지 선택하여 한눈에 비교 분석할 수 있습니다.
- **📌 핀 메뉴**: 자주 확인해야 하는 중요한 계산 결과는 대시보드 상단에 고정하여 즉시 확인할 수 있습니다.
- **🕒 히스토리**: 최근 수행한 계산 내역을 자동으로 저장하며, 개별 삭제가 가능합니다.

### 3. 사용자 경험 (UX/UI)
- **🎨 프리미엄 디자인**: 다크 모드 기반의 세련된 UI와 반응형 레이아웃을 제공합니다.
- **📱 PWA 지원**: 모바일 및 데스크탑에 앱처럼 설치하여 오프라인 환경에서도 사용할 수 있습니다.
- **📢 인터랙티브 차트**: Recharts를 활용한 동적 그래프와 상세 데이터 툴팁을 제공합니다.

## 🛠 기술 스택

- **Framework**: [Next.js 14 (App Router)](https://nextjs.org/)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **UI Components**: [shadcn/ui](https://ui.shadcn.com/)
- **State Management**: [Zustand](https://zustand-demo.pmnd.rs/)
- **Visualization**: [Recharts](https://recharts.org/)
- **Icons**: [Lucide React](https://lucide.dev/)

## 🚀 시작하기

### 개발 환경 설정

```bash
# 저장소 복제
git clone https://github.com/JoonChun/all-in-one_calculator.git

# 패키지 설치
npm install

# 로컬 실행
npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000)으로 접속하세요.

### PWA 설치
브라우저 주소창의 '설치' 아이콘을 클릭하여 앱으로 간편하게 사용할 수 있습니다.

## 📝 프로젝트 문서
- [PRD (제품 요구사항 정의서)](./prd.md)
- [UI/UX 점검 리포트](./ui_ux_review.md)

## 📄 라이선스
MIT License
