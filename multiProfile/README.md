# 💜 multiProfile (vi.joon Link)

AI와 감성으로 구축하는 개인 프로젝트 아카이브 및 성장형 포트폴리오 사이트입니다.

## ✨ 핵심 컨셉

'바이브 코딩(Claude + Antigravity)'을 통해 만든 결과물들을 기록하고 일반인에게 그 가능성을 전달하는 미니멀하고 트렌디한 링크 페이지입니다.

## 🛠️ 주요 기능

- **동적 렌더링**: `data.js`의 설정을 기반으로 포트폴리오를 실시간 생성
- **AI 챗봇**: Gemini 2.5 Flash 기반의 맞춤형 프로젝트 큐레이터
- **로컬 어드민 패널**: `Ctrl + M`을 통해 프로필과 링크를 즉시 수정 및 미리보기
- **API 키 분리**: API 키를 `.env.js`로 분리하여 Git에서 제외 (클라이언트 사이드 특성상 브라우저 DevTools에서는 노출될 수 있으므로, Google Cloud Console에서 사용량 제한 설정 권장)
- **3-Step 가이드**: 비개발자도 따라 만들 수 있도록 `guide/`에 단계별 HTML 튜토리얼 제공

## 🚀 실행 방법

이 프로젝트는 별도의 빌드 과정이 필요 없는 Vanilla JS로 제작되었습니다.

1. 프로젝트 루트에 `.env.js` 파일을 생성하고 Gemini API 키를 입력합니다.
   ```js
   // .env.js (Git에서 제외됨)
   window.ENV = {
     GEMINI_API_KEY: "your-api-key-here"
   };
   ```
2. `index.html`을 브라우저에서 열거나, 로컬 정적 서버로 호스팅합니다.
   ```bash
   # 예: Python 표준 서버
   python3 -m http.server 8000
   # → http://localhost:8000
   ```

## 🛠 어드민 패널

페이지에서 `Ctrl + M`을 누르면 어드민 패널이 열립니다. 프로필, 링크, 카테고리를 즉시 수정·미리보기할 수 있고, 변경 사항은 `data.js`로 내보내 커밋할 수 있습니다.

## 📁 프로젝트 구조

```text
multiProfile/
├── index.html        # 메인 페이지 (포트폴리오 + 챗봇)
├── app.js            # 동적 렌더링·라우팅·챗봇 로직
├── data.js           # 프로필·링크·프로젝트 메타데이터
├── build-env.js      # 빌드 시 .env.js 주입 헬퍼
├── index.css         # 커스텀 스타일
├── assets/           # 이미지·아이콘
├── docs/             # 블로그·서브 콘텐츠
├── guide/            # 3-step 가이드 (step1~3.html)
└── vercel.json       # Vercel 배포 설정
```

## 🌐 배포

Vercel에 정적 사이트로 배포되도록 `vercel.json`이 포함되어 있습니다. `vercel --prod` 또는 GitHub 연동으로 자동 배포할 수 있습니다.

## ⚠️ 보안 노트

`.env.js`의 키는 클라이언트 번들에 포함되어 브라우저에서 추출 가능합니다. 다음을 권장합니다.

- Google Cloud Console에서 키별 **HTTP 리퍼러 제한** 설정
- 일일 호출 한도(quota) 설정
- 프로덕션 트래픽 발생 시 서버리스 프록시 도입 검토

---
*Developed with Antigravity*
