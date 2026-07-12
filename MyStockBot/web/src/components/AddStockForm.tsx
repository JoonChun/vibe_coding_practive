import { useState, type FormEvent } from "react";
import { addWatchlistItem, ApiError } from "../api";

interface AddStockFormProps {
  /** 등록 성공 시 관심종목 재조회를 위해 호출 */
  onAdded: () => void;
}

const CODE_PATTERN = /^\d{1,6}$/;

export function AddStockForm({ onAdded }: AddStockFormProps) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trimmedCode = code.trim();
  const trimmedName = name.trim();
  const isCodeInvalid = trimmedCode.length > 0 && !CODE_PATTERN.test(trimmedCode);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!CODE_PATTERN.test(trimmedCode)) {
      setError("종목코드는 1~6자리 숫자로 입력해주세요.");
      return;
    }
    if (trimmedName.length === 0) {
      setError("종목명을 입력해주세요.");
      return;
    }

    setSubmitting(true);
    try {
      await addWatchlistItem({ code: trimmedCode, name: trimmedName });
      setCode("");
      setName("");
      onAdded();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "종목 추가에 실패했습니다."
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="add-stock-form" onSubmit={(e) => void handleSubmit(e)}>
      <div className="add-stock-form__fields">
        <label className="add-stock-form__field">
          <span>종목코드</span>
          <input
            type="text"
            inputMode="numeric"
            maxLength={6}
            placeholder="005930"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ""))}
            aria-label="종목코드, 1에서 6자리 숫자"
            aria-invalid={isCodeInvalid}
            disabled={submitting}
          />
        </label>
        <label className="add-stock-form__field">
          <span>종목명</span>
          <input
            type="text"
            placeholder="삼성전자"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="종목명"
            disabled={submitting}
          />
        </label>
        <button
          type="submit"
          className="add-stock-form__submit"
          aria-label="관심종목 추가"
          disabled={submitting}
        >
          {submitting ? "추가 중…" : "추가"}
        </button>
      </div>
      {error ? (
        <p className="add-stock-form__error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}
