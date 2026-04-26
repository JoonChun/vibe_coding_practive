# mapf-analyzer (React + Vite 앱)

[MAPF Post-Mortem Analyzer](../README.md)의 프론트엔드 앱입니다. 상세한 기능·아키텍처 설명은 상위 README를 참고하세요.

## 스크립트

| 명령 | 설명 |
| --- | --- |
| `npm run dev` | Vite 개발 서버 실행 (HMR) |
| `npm run build` | TypeScript 검증 후 프로덕션 빌드 (`dist/`) |
| `npm run preview` | 빌드 결과 미리보기 |
| `npm run lint` | ESLint 검사 |

## 환경 변수

Gemini 프록시(BFF)를 사용하려면 Vercel Serverless 환경에 `GEMINI_API_KEY`를 등록하세요. 로컬에서는 `api/` 핸들러가 호출되지 않는 한 키 없이도 핵심 분석 기능(파싱·그래프 추출·Re-plan)은 동작합니다.

## 기술 스택

- React 18 + Vite + TypeScript
- Zustand (상태), React Flow (그래프), Tailwind CSS v4
- Web Workers (A*, DFS), Canvas 2D
- `@google/genai` (스키마 어댑터)
