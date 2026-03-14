# 💜 multiProfile (vi.joon Link)

AI와 감성으로 구축하는 개인 프로젝트 아카이브 및 성장형 포트폴리오 사이트입니다.

## ✨ 핵심 컨셉

'바이브 코딩(Claude + Antigravity)'을 통해 만든 결과물들을 기록하고 일반인에게 그 가능성을 전달하는 미니멀하고 트렌디한 링크 페이지입니다.

## 🛠️ 주요 기능

- **동적 렌더링**: `data.js`의 설정을 기반으로 포트폴리오를 실시간 생성
- **AI 챗봇**: Gemini 2.5 Flash 기반의 맞춤형 프로젝트 큐레이터
- **로컬 어드민 패널**: `Ctrl + M`을 통해 프로필과 링크를 즉시 수정 및 미리보기
- **API 키 분리**: API 키를 `.env.js`로 분리하여 Git에서 제외 (클라이언트 사이드 특성상 브라우저 DevTools에서는 노출될 수 있으므로, Google Cloud Console에서 사용량 제한 설정 권장)

## 🚀 실행 방법

이 프로젝트는 별도의 빌드 과정이 필요 없는 Vanilla JS로 제작되었습니다.

1. `.env.js` 파일을 생성하고 Gemini API 키를 입력합니다.
2. `index.html`을 브라우저에서 실행합니다.

---
*Developed with Antigravity*
