import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { ApiError, getWhatIf } from "../api";
import type { WhatIfResponse } from "../types";
import { epochToKstDateStr, formatKrw, objectParticle } from "../utils/format";
import { STATUS_COLOR } from "./PullbackCard";
import { SignalChip } from "./SignalChip";

export interface TimeMachineCardHandle {
  /** BottomSheet가 열릴 때(§12 "첫 포커스는 날짜 입력") 호출 — 프리필된 값 확인이 우선이므로. */
  focusDate: () => void;
}

interface TimeMachineCardProps {
  code: string;
  /** 서브라인·공유 문구에 쓰는 종목명 */
  name: string;
  /** "sheet"면 결과 상태에서 폼을 접고 "‹ 다시 계산하기"로 전환(§5-3). 기본은 "inline"(§4-3, 폼+결과 동시 노출) */
  variant?: "inline" | "sheet";
  /** 차트 봉 탭으로 프리필된 매수일(YYYY-MM-DD, §7-2) — sheet 변형에서만 사용 */
  initialDate?: string;
  /** 이번 세션 마지막 계산 금액(§7-2) — 없으면 기본값 100만원 */
  initialAmount?: number;
  /** 계산 실행 시(제출 시점) 상위로 알려 "마지막 사용 금액"을 세션 동안 기억하게 함 */
  onAmountUsed?: (amount: number) => void;
  /** variant="sheet"에서 BottomSheet의 aria-labelledby와 동일해야 하는 헤더 id */
  titleId?: string;
}

type ResultState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; data: WhatIfResponse }
  | { kind: "known-error"; message: string }
  | { kind: "generic-error" };

const DEFAULT_AMOUNT = 1_000_000;
const AMOUNT_PRESETS: { value: number; label: string }[] = [
  { value: 100_000, label: "10만" },
  { value: 1_000_000, label: "100만" },
  { value: 10_000_000, label: "1000만" },
];
const MAX_AMOUNT = 100_000_000;
const RESULT_DISCLAIMER = "ⓘ 단순 가격 기준 · 배당/분할/수수료 미반영 · 모의 계산";

function formatSignedKrw(value: number): string {
  return `${value >= 0 ? "+" : ""}${formatKrw(value)}원`;
}

function formatSignedPct(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

/**
 * Phase 3 "그날의 나" 타임머신(What-if) — 폼(날짜·금액·프리셋·CTA) + 결과(성공/에러) + 로딩을
 * 한 컴포넌트가 소유(docs/wireframes/phase3-timemachine.md §8). StockDetailPage 인라인 섹션(화면1)과
 * BottomSheet 내부(화면2) 양쪽에서 `variant`만 바꿔 재사용한다.
 */
export const TimeMachineCard = forwardRef<TimeMachineCardHandle, TimeMachineCardProps>(
  function TimeMachineCard(
    { code, name, variant = "inline", initialDate, initialAmount, onAmountUsed, titleId },
    ref
  ) {
    const [date, setDate] = useState(initialDate ?? "");
    const [amount, setAmount] = useState(initialAmount ?? DEFAULT_AMOUNT);
    const [resultState, setResultState] = useState<ResultState>({ kind: "idle" });
    const [announcement, setAnnouncement] = useState("");

    const dateInputRef = useRef<HTMLInputElement>(null);
    const lastParamsRef = useRef<{ date: string; amount: number } | null>(null);

    useImperativeHandle(ref, () => ({
      focusDate: () => dateInputRef.current?.focus(),
    }));

    const loading = resultState.kind === "loading";
    const todayStr = epochToKstDateStr(Math.floor(Date.now() / 1000));
    const showingForm = variant === "inline" || resultState.kind === "idle" || loading;
    const showingBackLink = variant === "sheet" && !showingForm;
    const supportsShare =
      typeof navigator !== "undefined" && typeof navigator.share === "function";

    async function runCalculation(paramDate: string, paramAmount: number) {
      setResultState({ kind: "loading" });
      lastParamsRef.current = { date: paramDate, amount: paramAmount };
      try {
        const res = await getWhatIf(code, paramDate, paramAmount);
        if (res.error) {
          setResultState({ kind: "known-error", message: res.error });
          setAnnouncement(`오류: ${res.error}`);
        } else {
          setResultState({ kind: "success", data: res });
          setAnnouncement("계산 완료");
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setResultState({ kind: "known-error", message: err.message });
          setAnnouncement(`오류: ${err.message}`);
        } else {
          setResultState({ kind: "generic-error" });
          setAnnouncement("오류: 계산하지 못했습니다");
        }
      }
      onAmountUsed?.(paramAmount);
    }

    function handleSubmit(e: FormEvent<HTMLFormElement>) {
      e.preventDefault();
      if (!date || amount <= 0 || loading) return;
      void runCalculation(date, amount);
    }

    function handleAmountInput(e: ChangeEvent<HTMLInputElement>) {
      const digitsOnly = e.target.value.replace(/[^0-9]/g, "");
      const parsed = digitsOnly === "" ? 0 : Math.min(Number(digitsOnly), MAX_AMOUNT);
      setAmount(parsed);
    }

    function handleBackToForm() {
      setResultState({ kind: "idle" });
    }

    function handleRetryFocusDate() {
      setResultState({ kind: "idle" });
      dateInputRef.current?.focus();
    }

    function handleRetrySameParams() {
      const params = lastParamsRef.current;
      if (!params) {
        setResultState({ kind: "idle" });
        return;
      }
      void runCalculation(params.date, params.amount);
    }

    async function handleShare(shareText: string) {
      const url = window.location.href;
      if (supportsShare) {
        try {
          await navigator.share({ title: "그날의 나 — MyStockBot", text: shareText, url });
        } catch {
          // 사용자가 공유를 취소한 경우 등 — 조용히 무시
        }
        return;
      }
      try {
        await navigator.clipboard.writeText(`${shareText}\n${url}`);
        setAnnouncement("링크가 복사되었습니다");
      } catch {
        // 클립보드 접근 실패 — 과도한 에러 UI 없이 조용히 무시
      }
    }

    function renderResultArea() {
      if (resultState.kind === "idle") return null;

      if (resultState.kind === "loading") {
        return (
          <div className="timemachine-result timemachine-result--loading" role="status">
            <span className="candle-chart__spinner" aria-hidden="true" />
            <p>계산하고 있어요</p>
          </div>
        );
      }

      if (resultState.kind === "known-error") {
        return (
          <div className="timemachine-result timemachine-result--empty">
            <span className="timemachine-result__empty-icon" aria-hidden="true">
              🕰
            </span>
            <p className="timemachine-result__empty-message">{resultState.message}</p>
            <button
              type="button"
              className="panel__back-link timemachine-card__retry"
              onClick={handleRetryFocusDate}
            >
              다른 날짜로 다시 시도
            </button>
            <p className="timemachine-result__disclaimer">{RESULT_DISCLAIMER}</p>
          </div>
        );
      }

      if (resultState.kind === "generic-error") {
        return (
          <div className="timemachine-result timemachine-result--empty">
            <span className="timemachine-result__empty-icon" aria-hidden="true">
              🕰
            </span>
            <p className="timemachine-result__empty-message">계산하지 못했습니다</p>
            <p className="timemachine-result__empty-submessage">잠시 후 다시 시도해주세요</p>
            <button
              type="button"
              className="panel__back-link timemachine-card__retry"
              onClick={handleRetrySameParams}
            >
              다시 시도
            </button>
            <p className="timemachine-result__disclaimer">{RESULT_DISCLAIMER}</p>
          </div>
        );
      }

      const data = resultState.data;
      const multiple = data.multiple ?? 0;
      const returnPct = data.return_pct ?? 0;
      const evalAmount = data.eval_amount ?? 0;
      const profit = data.profit ?? 0;
      const isProfit = profit >= 0;

      const [by, bm, bd] = data.buy_date ? data.buy_date.split("-").map(Number) : [];
      const headline = data.buy_date ? `${by}년 ${bm}월 ${bd}일의 나에게` : "";
      const subline = `그때 ${formatKrw(data.amount)}원으로 ${name}${objectParticle(name)} 샀다면`;

      const kospiMultiple = data.kospi?.multiple ?? null;
      const maxMultiple = Math.max(multiple, kospiMultiple ?? 0, 0.01);
      const stockBarWidth = Math.max((multiple / maxMultiple) * 100, 4);
      const kospiBarWidth =
        kospiMultiple !== null ? Math.max((kospiMultiple / maxMultiple) * 100, 4) : 0;

      const shareText = `${headline}\n${subline}\n${multiple.toFixed(1)}배 (${formatSignedPct(returnPct)})`;

      return (
        <div className="timemachine-result">
          <p className="timemachine-result__headline">{headline}</p>
          <p className="timemachine-result__subline">{subline}</p>

          <div
            className={`timemachine-result__hero${
              isProfit ? " timemachine-result__hero--up" : " timemachine-result__hero--down"
            }`}
          >
            <span className="timemachine-result__hero-multiple">{multiple.toFixed(1)}배</span>
            <span className="timemachine-result__hero-pct">{formatSignedPct(returnPct)}</span>
          </div>

          <p className="timemachine-result__principal">
            {formatKrw(data.amount)}원 → {formatKrw(evalAmount)}원 ({formatSignedKrw(profit)})
          </p>

          <hr className="timemachine-result__divider" />

          <div className="timemachine-result__compare">
            <div className="timemachine-result__compare-row">
              <span className="timemachine-result__compare-label">이 종목</span>
              <div className="timemachine-result__compare-track">
                <div
                  className={`timemachine-result__compare-fill${
                    isProfit
                      ? " timemachine-result__compare-fill--up"
                      : " timemachine-result__compare-fill--down"
                  }`}
                  style={{ width: `${stockBarWidth}%` }}
                />
              </div>
              <span className="timemachine-result__compare-value">
                {multiple.toFixed(1)}배 ({formatSignedPct(returnPct)})
              </span>
            </div>
            {data.kospi ? (
              <div className="timemachine-result__compare-row">
                <span className="timemachine-result__compare-label">코스피면</span>
                <div className="timemachine-result__compare-track">
                  <div
                    className={`timemachine-result__compare-fill${
                      data.kospi.profit >= 0
                        ? " timemachine-result__compare-fill--up"
                        : " timemachine-result__compare-fill--down"
                    }`}
                    style={{ width: `${kospiBarWidth}%` }}
                  />
                </div>
                <span className="timemachine-result__compare-value">
                  {data.kospi.multiple.toFixed(1)}배 ({formatSignedPct(data.kospi.return_pct)})
                </span>
              </div>
            ) : null}
          </div>

          {data.bot_judgment ? (
            <>
              <hr className="timemachine-result__divider" />
              <div className="timemachine-result__judgment">
                <div className="timemachine-result__judgment-header">
                  <SignalChip label={data.bot_judgment.long_view} kind="그날 봇" variant="confirmed" />
                  <span className="timemachine-result__judgment-title">그날 봇 판정</span>
                </div>
                <p className="timemachine-result__judgment-factors">
                  MACD {data.bot_judgment.macd_1d ?? "—"} · RSI {data.bot_judgment.rsi_1d ?? "—"}
                </p>
                {data.bot_judgment.pullback_status ? (
                  <span
                    className="pullback-card__chip timemachine-result__pullback-chip"
                    style={{
                      color: STATUS_COLOR[data.bot_judgment.pullback_status],
                      borderColor: STATUS_COLOR[data.bot_judgment.pullback_status],
                    }}
                  >
                    {data.bot_judgment.pullback_status}
                  </span>
                ) : null}
                <p className="timemachine-result__judgment-note">ⓘ {data.bot_judgment.note}</p>
              </div>
            </>
          ) : null}

          <hr className="timemachine-result__divider" />

          <div className="timemachine-result__actions">
            <button
              type="button"
              className="timemachine-result__share"
              onClick={() => void handleShare(shareText)}
            >
              <span aria-hidden="true">⤴</span> {supportsShare ? "공유하기" : "링크 복사"}
            </button>
          </div>
          <p className="timemachine-result__disclaimer">{RESULT_DISCLAIMER}</p>
        </div>
      );
    }

    return (
      <div className={`timemachine-card${variant === "sheet" ? " timemachine-card--sheet" : ""}`}>
        <div className="timemachine-card__header">
          {showingBackLink ? (
            <button type="button" className="timemachine-card__back" onClick={handleBackToForm}>
              <span aria-hidden="true">‹</span> 다시 계산하기
            </button>
          ) : (
            <div>
              <h3 id={titleId} className="timemachine-card__title">
                그날의 나 <span className="timemachine-card__title-en">Time Machine</span>
              </h3>
              {variant === "inline" ? (
                <p className="timemachine-card__intro">
                  과거 매수일과 금액을 넣으면 지금 가치를 계산해드립니다
                </p>
              ) : null}
            </div>
          )}
        </div>

        {showingForm ? (
          <form className="timemachine-card__form" onSubmit={handleSubmit}>
            <label className="timemachine-card__field">
              <span className="timemachine-card__field-label">매수일</span>
              <input
                ref={dateInputRef}
                type="date"
                className="timemachine-card__date-input"
                value={date}
                max={todayStr}
                disabled={loading}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </label>
            <p className="timemachine-card__hint">조회 가능한 데이터는 최근 약 4년입니다</p>

            <label className="timemachine-card__field">
              <span className="timemachine-card__field-label">투자 금액</span>
              <div className="timemachine-card__amount-input-wrap">
                <input
                  type="text"
                  inputMode="numeric"
                  className="timemachine-card__amount-input"
                  value={amount > 0 ? formatKrw(amount) : ""}
                  disabled={loading}
                  onChange={handleAmountInput}
                  aria-label="투자 금액(원)"
                />
                <span className="timemachine-card__amount-unit" aria-hidden="true">
                  원
                </span>
              </div>
            </label>

            <div className="timemachine-card__presets" role="group" aria-label="투자 금액 프리셋">
              {AMOUNT_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  className={`tf-bar__btn${amount === preset.value ? " tf-bar__btn--active" : ""}`}
                  aria-pressed={amount === preset.value}
                  disabled={loading}
                  onClick={() => setAmount(preset.value)}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            <button
              type="submit"
              className="search-bar__add-submit timemachine-card__submit"
              disabled={loading || !date || amount <= 0}
            >
              {loading ? (
                <>
                  <span className="candle-chart__spinner timemachine-card__spinner-sm" aria-hidden="true" />
                  계산 중…
                </>
              ) : (
                "계산하기"
              )}
            </button>
          </form>
        ) : null}

        {renderResultArea()}

        <span className="sr-only" role="status" aria-live="polite">
          {announcement}
        </span>
      </div>
    );
  }
);
