import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { setApiToken } from "./api";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";

// 매직 링크 온보딩: https://…/#token=<값> 으로 접속하면 토큰을 저장하고
// 주소에서 즉시 지운다. fragment(#)는 서버·프록시 로그에 남지 않지만
// 브라우저 히스토리에는 남으므로 replaceState 로 흔적을 제거한다.
// (개인 3인용 공유 편의 — 링크 클릭 한 번이면 토큰 입력 불필요)
const hashToken = new URLSearchParams(window.location.hash.slice(1)).get("token");
if (hashToken) {
  setApiToken(hashToken);
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("루트 엘리먼트(#root)를 찾을 수 없습니다.");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
