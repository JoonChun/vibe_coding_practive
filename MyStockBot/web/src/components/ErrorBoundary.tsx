import { Component, type ErrorInfo, type ReactNode } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * 앱 최상위 에러 경계.
 *
 * 각 페이지는 옵셔널 체이닝으로 결측 데이터를 꼼꼼히 막고 있지만, 예상 못 한 응답
 * 형태(스키마가 바뀐 백엔드, 손상된 JSON)로 **렌더 중** 예외가 던져지면 React 가
 * 트리 전체를 언마운트해 백지가 된다. PWA 로 설치해 쓰는 경우 그 상태에서 할 수
 * 있는 일이 없으므로, 최소한 무슨 일이 났는지와 복구 수단을 남긴다.
 *
 * 클래스 컴포넌트인 이유: componentDidCatch/getDerivedStateFromError 는 React 19
 * 기준으로도 훅 대응물이 없다.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 개인용 앱이라 원격 수집처가 없다 — 콘솔이 유일한 사후 단서다.
    console.error("[ErrorBoundary] 렌더 중 예외:", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="app">
        <main className="dash-main">
          <section className="error-boundary" role="alert">
            <h1 className="error-boundary__title">화면을 그리지 못했습니다</h1>
            <p className="error-boundary__body">
              예상하지 못한 오류가 발생했습니다. 새로고침하면 대부분 복구됩니다.
              계속 반복되면 서버 응답 형식이 바뀌었을 수 있습니다.
            </p>
            <p className="error-boundary__detail">{error.message}</p>
            <button
              type="button"
              className="banner__retry"
              onClick={() => window.location.reload()}
            >
              새로고침
            </button>
          </section>
        </main>
      </div>
    );
  }
}
