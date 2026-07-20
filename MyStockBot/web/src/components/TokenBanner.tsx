import { useId, useState, type FormEvent } from "react";
import { setApiToken } from "../api";

interface TokenBannerProps {
  /** 토큰 저장 후 관심종목·스냅샷 재조회 등 후속 처리를 위해 호출 */
  onSaved: () => void;
}

export function TokenBanner({ onSaved }: TokenBannerProps) {
  const [token, setToken] = useState("");
  const [show, setShow] = useState(false);
  const inputId = useId();

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const trimmed = token.trim();
    if (trimmed.length === 0) return;
    setApiToken(trimmed);
    setToken("");
    onSaved();
  }

  return (
    <div className="banner banner--warning" role="alert">
      <form className="token-banner" onSubmit={handleSubmit}>
        <span className="token-banner__message">API 토큰이 필요합니다</span>
        <p className="token-banner__help">
          서버 배포 시 환경변수 <code>MYSTOCKBOT_API_TOKEN</code> 에 설정한 값을
          입력하세요. 설정 방법은 저장소의 <code>DEPLOY.md</code> 를 참고하세요. 토큰은
          이 브라우저에만 저장됩니다.
        </p>
        <label className="token-banner__field" htmlFor={inputId}>
          <span>API 토큰</span>
          <div className="token-banner__input-wrap">
            <input
              id={inputId}
              type={show ? "text" : "password"}
              placeholder="예: mysb_live_xxxxxxxx"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              aria-label="API 토큰"
              autoComplete="off"
            />
            <button
              type="button"
              className="token-banner__toggle"
              onClick={() => setShow((v) => !v)}
              aria-label={show ? "토큰 숨기기" : "토큰 표시"}
            >
              {show ? "숨김" : "표시"}
            </button>
          </div>
        </label>
        <button
          type="submit"
          className="token-banner__submit"
          aria-label="API 토큰 저장"
          disabled={token.trim().length === 0}
        >
          저장
        </button>
      </form>
    </div>
  );
}
