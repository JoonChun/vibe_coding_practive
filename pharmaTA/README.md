# 💊 PharmaTA Insight

> AI 기반 질환군(TA, Therapeutic Area)별 제약·바이오 데이터 인사이트 플랫폼

방대하게 흩어진 임상·공시·뉴스 데이터를 7대 질환군 단위로 자동 분류·요약하여 구조화된 인사이트로 전환합니다.

## 📌 현재 상태

> 🚧 **기획 단계** — PRD가 정의되어 있고, 구현은 아직 시작되지 않았습니다. 현재 디렉토리에는 [`prd.md`](./prd.md)만 포함되어 있습니다.

## 🎯 타깃 사용자

| 페르소나 | 시나리오 |
| --- | --- |
| **현직자 (연구/전략)** | 관심 TA(예: Metabolic) 탭에서 글로벌 임상 3상 결과 및 경쟁사 동향 요약을 확인하고 팀에 공유 |
| **취업 준비생** | 면접 전 타겟 기업의 파이프라인 중 주력 TA 비중을 차트로 확인하고 R&D 타임라인을 정리 |

## ✨ 핵심 기능 (예정)

1. **Gemini 기반 지능형 분류** — 뉴스·공시를 7대 TA 또는 'Other'로 자동 매핑하고 3줄 요약 생성
2. **HITL 피드백 교정** — 분류 오류를 사용자가 수정 → Few-shot 데이터로 누적되어 자가 학습
3. **기업별 TA 포트폴리오** — R&D 집중 분야 시각화 + 타임라인 히스토리
4. **원문 소스 추적** — 모든 데이터에 식약처/FDA/뉴스 원문 다이렉트 링크 병기
5. **모바일 퍼스트 대시보드** — 이동 중에도 최적화되는 반응형 레이아웃

## 🛠 기술 스택 (예정)

| 구분 | 스택 |
| --- | --- |
| **Frontend** | Next.js (App Router), Tailwind CSS, shadcn/ui |
| **Backend** | FastAPI (Python) |
| **AI** | Gemini 1.5 Pro / Flash (Google AI SDK) |
| **Database** | PostgreSQL + pgvector, Supabase |
| **Infrastructure** | Vercel (FE), Railway/Render (BE) |

## 🎨 디자인 톤 (요약)

- **Theme**: Pure White (`#FFFFFF`) & Deep Black (`#09090B`) 미니멀리즘
- **Accent**: Purple-600 (전문성 강조용 제한적 사용)
- **Typography**: Pretendard

## 📄 참고 문서

- [PRD (제품 요구사항 정의서)](./prd.md)

---
*Planned by vi.joon*
