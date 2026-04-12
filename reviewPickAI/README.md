# ReviewPick AI

쿠팡·네이버 쇼핑의 리뷰를 자동 수집하고 AI로 분석해주는 크롬 익스텐션입니다.  
수천 건의 리뷰를 직접 읽지 않아도 감성 분석, 키워드 마인드맵, 마케팅 인사이트를 즉시 확인할 수 있습니다.

---

## 주요 기능

| 기능 | 설명 |
| ------ | ------ |
| **스마트 크롤러** | 쿠팡 / 네이버 쇼핑 상품 페이지의 리뷰를 자동 수집 (페이지네이션 처리) |
| **AI 인사이트 요약** | Google Gemini API가 핵심 내용 3줄 요약 + 마케팅 포인트 제공 |
| **감성 분석** | 긍정 / 부정 / 중립 비율을 도넛 차트로 시각화 |
| **키워드 마인드맵** | 키워드 빈도·관계를 D3.js 방사형 트리로 인터랙티브하게 표현 |
| **키워드 필터 재분석** | 특정 키워드로 리뷰를 필터링해 세분화된 분석 재실행 |
| **비교 분석** | 2개 이상의 제품을 나란히 비교 |
| **다양한 내보내기** | PDF(대시보드 스냅샷), CSV(원본 리뷰), PNG(마인드맵) 지원 |

---

## 기술 스택

- **프레임워크:** React 18, TypeScript
- **스타일링:** Tailwind CSS (Blue Horizon 디자인 시스템)
- **시각화:** D3.js (마인드맵), Chart.js (감성 차트)
- **AI:** Google Gemini API (`gemini-3-flash-preview`)
- **빌드:** Vite (Manifest V3 멀티 엔트리)
- **내보내기:** html2canvas, jsPDF

---

## 시작하기

### 요구 사항

- Node.js 18 이상
- Google Gemini API 키 ([Google AI Studio](https://aistudio.google.com/)에서 발급)

### 설치 및 빌드

```bash
cd reviewPickAI
npm install
npm run build
```

### 크롬에 로드

1. `chrome://extensions` 접속
2. 우측 상단 **개발자 모드** 활성화
3. **압축 해제된 확장 프로그램 로드** 클릭 → `dist/` 폴더 선택

### 사용 방법

1. 익스텐션 팝업을 열어 **Gemini API 키** 입력
2. 쿠팡 또는 네이버 쇼핑 상품 상세 페이지로 이동
3. 팝업에서 **분석 시작** 클릭
4. 수집 → AI 분석 완료 후 대시보드가 자동으로 열림

---

## 프로젝트 구조

```text
reviewPickAI/
├── src/
│   ├── background/       # 서비스 워커 (분석 파이프라인 오케스트레이션)
│   ├── content/          # 콘텐츠 스크립트 (크롤러: Coupang / Naver)
│   ├── dashboard/        # 대시보드 UI (React 컴포넌트 + 훅)
│   ├── popup/            # 팝업 UI (분석 트리거 + 진행 상태, index.html 포함)
│   ├── gemini/           # Gemini API 클라이언트 + 프롬프트
│   ├── utils/            # 공통 유틸 (export.ts: PDF/CSV/PNG 내보내기, storage.ts: chrome.storage 래퍼)
│   ├── styles/           # 전역 스타일 (globals.css)
│   ├── types/            # TypeScript 인터페이스
│   ├── constants/        # 공통 상수 (Gemini 모델명, 크롤링 설정 등)
│   └── config/           # 플랫폼별 CSS 셀렉터
├── public/
│   ├── manifest.json     # Manifest V3 설정
│   └── icons/            # 익스텐션 아이콘
├── pages/                # HTML 엔트리 포인트 (dashboard.html, popup.html)
├── dist/                 # 빌드 결과물
└── prd.md                # 제품 요구사항 문서
```

---

## 데이터 흐름

```text
팝업 [분석 시작]
  → 콘텐츠 스크립트: 쿠팡/네이버 크롤링 (페이지당 CRAWL_PROGRESS 전송)
  → 백그라운드: 100개 단위 청크로 Gemini API 순차 호출
  → 청크 결과 병합 → chrome.storage.local 저장
  → 대시보드 탭 자동 오픈 → 분석 결과 렌더링
```

### 키워드 필터 재분석 흐름

```text
사이드바 키워드 입력 → 해당 키워드 포함 리뷰만 필터링
  → Gemini 재분석 → 감성/키워드 업데이트 (원본 리뷰 목록 유지)
```

---

## 빌드 스크립트

| 명령어 | 설명 |
| -------- | ------ |
| `npm run dev` | 파일 변경 감지 후 자동 빌드 (개발 모드) |
| `npm run build` | 프로덕션 빌드 → `dist/` 생성 |
| `npm run type-check` | TypeScript 타입 검사 |

---

## 지원 플랫폼

| 플랫폼    | 상태 |
|--------|------|
| 쿠팡     | 지원 |
| 네이버 쇼핑 | 지원 |

---

## 주의 사항

- 수집된 데이터는 내부 분석 목적으로만 사용하세요.
- 과도한 크롤링은 플랫폼 이용약관에 위반될 수 있습니다. 요청 간 랜덤 딜레이가 적용되어 있습니다.
- Gemini API 사용량에 따라 비용이 발생할 수 있습니다.
