import { useId, useState, type FormEvent } from "react";
import { setApiToken } from "../api";

interface TokenBannerProps {
  /** 토큰 저장 후 관심종목·스냅샷 재조회 등 후속 처리를 위해 호출 */
  onSaved: () => void;
}

export function TokenBanner({ onSaved }: TokenBannerProps) {
  const [token, setToken] = useState("");
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
        <label className="token-banner__field" htmlFor={inputId}>
          <span>API 토큰</span>
          <input
            id={inputId}
            type="password"
            placeholder="API 토큰 입력"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            aria-label="API 토큰"
            autoComplete="off"
          />
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
