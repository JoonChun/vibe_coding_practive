import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { addWatchlistItem, ApiError, searchStocks } from "../api";
import type { SearchItem } from "../types";

interface AddStockFormProps {
  /** 검색어 — 아래 Watchlist 카드 목록 필터링에도 사용 */
  query: string;
  onQueryChange: (value: string) => void;
  /** 이미 등록된 종목코드 목록 — 6자리 코드 입력 시 신규 등록 가능 여부 판단 */
  existingCodes: ReadonlySet<string>;
  /** 등록 성공 시 관심종목 재조회를 위해 호출 */
  onAdded: () => void;
}

const SIX_DIGIT_CODE = /^\d{6}$/;
const SEARCH_DEBOUNCE_MS = 300;

const MARKET_BADGE_CLASS: Record<SearchItem["market"], string> = {
  KOSPI: "market-badge market-badge--kospi",
  KOSDAQ: "market-badge market-badge--kosdaq",
};

export function AddStockForm({
  query,
  onQueryChange,
  existingCodes,
  onAdded,
}: AddStockFormProps) {
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [results, setResults] = useState<SearchItem[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const containerRef = useRef<HTMLElement | null>(null);
  const listboxId = "stock-search-listbox";

  const trimmedQuery = query.trim();
  const isNewCode = useMemo(
    () => SIX_DIGIT_CODE.test(trimmedQuery) && !existingCodes.has(trimmedQuery),
    [trimmedQuery, existingCodes]
  );

  // 입력 300ms 디바운스 후 자동완성 검색. 언마운트/입력 변경 시 이전 요청 결과 무시.
  useEffect(() => {
    if (trimmedQuery.length === 0) {
      setResults([]);
      setOpen(false);
      setActiveIndex(-1);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(() => {
      searchStocks(trimmedQuery, 10)
        .then((res) => {
          if (cancelled) return;
          setResults(res.items);
          setOpen(res.items.length > 0);
          setActiveIndex(-1);
        })
        .catch(() => {
          if (cancelled) return;
          setResults([]);
          setOpen(false);
          setActiveIndex(-1);
        });
    }, SEARCH_DEBOUNCE_MS);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [trimmedQuery]);

  // 외부 클릭 시 드롭다운 닫힘
  useEffect(() => {
    function handlePointerDown(e: MouseEvent) {
      if (!containerRef.current) return;
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  async function selectItem(item: SearchItem) {
    if (existingCodes.has(item.code)) {
      // 이미 등록된 종목 — 드롭다운만 닫고 해당 카드로 스크롤
      setOpen(false);
      document
        .getElementById(`stock-card-${item.code}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    setOpen(false);
    setError(null);
    setSubmitting(true);
    try {
      await addWatchlistItem({ code: item.code, name: item.name });
      onQueryChange("");
      onAdded();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "종목 추가에 실패했습니다."
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleInputKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (!open || results.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      if (activeIndex >= 0 && activeIndex < results.length) {
        e.preventDefault();
        void selectItem(results[activeIndex]);
      }
    } else if (e.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    const trimmedName = name.trim();
    if (trimmedName.length === 0) {
      setError("종목명을 입력해주세요.");
      return;
    }

    setSubmitting(true);
    try {
      await addWatchlistItem({ code: trimmedQuery, name: trimmedName });
      setName("");
      onQueryChange("");
      onAdded();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "종목 추가에 실패했습니다."
      );
    } finally {
      setSubmitting(false);
    }
  }

  const activeOptionId =
    activeIndex >= 0 && activeIndex < results.length
      ? `stock-search-option-${results[activeIndex].code}`
      : undefined;

  return (
    <section
      className="search-bar"
      role="search"
      aria-label="종목 검색 및 추가"
      ref={containerRef}
    >
      <label className="sr-only" htmlFor="stock-search-input">
        종목명 또는 코드 검색
      </label>
      <div className="search-bar__combo">
        <div className="search-bar__input-wrap">
          <svg
            className="search-bar__icon"
            aria-hidden="true"
            viewBox="0 0 24 24"
            width="20"
            height="20"
          >
            <path
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              d="M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm9 2-4.35-4.35"
            />
          </svg>
          <input
            id="stock-search-input"
            type="text"
            placeholder="종목명 또는 코드 검색"
            value={query}
            onChange={(e) => {
              onQueryChange(e.target.value);
              setError(null);
            }}
            onFocus={() => {
              if (results.length > 0) setOpen(true);
            }}
            onKeyDown={handleInputKeyDown}
            className="search-bar__input"
            autoComplete="off"
            role="combobox"
            aria-expanded={open}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={activeOptionId}
          />
        </div>

        {open && results.length > 0 ? (
          <ul
            className="search-dropdown"
            role="listbox"
            id={listboxId}
            aria-label="종목 검색 결과"
          >
            {results.map((item, index) => {
              const registered = existingCodes.has(item.code);
              const active = index === activeIndex;
              return (
                <li
                  key={item.code}
                  id={`stock-search-option-${item.code}`}
                  role="option"
                  aria-selected={active}
                  className={`search-dropdown__item${
                    active ? " search-dropdown__item--active" : ""
                  }`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    void selectItem(item);
                  }}
                  onMouseEnter={() => setActiveIndex(index)}
                >
                  <span className="search-dropdown__info">
                    <span className="search-dropdown__name">{item.name}</span>
                    <span className="search-dropdown__code">{item.code}</span>
                  </span>
                  <span className="search-dropdown__meta">
                    {registered ? (
                      <span className="search-dropdown__registered">
                        등록됨
                      </span>
                    ) : null}
                    <span className={MARKET_BADGE_CLASS[item.market]}>
                      {item.market}
                    </span>
                  </span>
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>

      {isNewCode && !open ? (
        <form
          className="search-bar__add"
          onSubmit={(e) => void handleSubmit(e)}
        >
          <span className="search-bar__add-label">
            신규 종목 <strong>{trimmedQuery}</strong> 관심종목에 추가
          </span>
          <label className="search-bar__add-field">
            <span className="sr-only">종목명</span>
            <input
              type="text"
              placeholder="종목명 입력 (예: 삼성전자)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label="종목명"
              disabled={submitting}
            />
          </label>
          <button
            type="submit"
            className="search-bar__add-submit"
            aria-label={`${trimmedQuery} 관심종목 추가`}
            disabled={submitting}
          >
            {submitting ? "추가 중…" : "추가"}
          </button>
        </form>
      ) : null}

      {error ? (
        <p className="add-stock-form__error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
