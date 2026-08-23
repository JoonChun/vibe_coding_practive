import type { MarketStatus, MarketStatusCode } from "../types";

interface MarketStatusBarProps {
  data: MarketStatus | null;
  remainingMs: number | null;
  countdownTarget: "close" | "open" | null;
  /** "방금" / "3초 전" 등 — 마지막 스냅샷 갱신 시각 */
  updatedRelative: string;
}

/** 상태별 배지 색. 상승/하락 의미색(빨강/파랑)과 겹치지 않게 중립 톤을 쓴다. */
const STATUS_CLASS: Record<MarketStatusCode, string> = {
  open: "market-bar__badge--open",
  pre: "market-bar__badge--pre",
  closed: "market-bar__badge--closed",
  holiday: "market-bar__badge--holiday",
};

function formatRemaining(ms: number): string {
  const totalMinutes = Math.floor(ms / 60_000);
  const days = Math.floor(totalMinutes / (60 * 24));
  const hours = Math.floor((totalMinutes % (60 * 24)) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) return `${days}일 ${hours}시간`;
  if (hours > 0) return `${hours}시간 ${minutes}분`;
  if (minutes > 0) return `${minutes}분`;
  return "1분 미만";
}

function formatMonthDay(isoDate: string): string {
  const [, month, day] = isoDate.split("-");
  if (!month || !day) return isoDate;
  return `${Number(month)}월 ${Number(day)}일`;
}

/**
 * 시장 상태 줄 — PRD §10.1 블록2.
 *
 * `market_calendar` 는 예전부터 있었지만 이를 화면에 노출하는 경로가 없어서, 사용자는
 * 지금 보이는 시세가 오늘 것인지 지난 거래일 것인지 알 수 없었다. 휴장·장전에는
 * "최근 거래일 기준"을 명시해 신선도를 오해하지 않게 한다.
 */
export function MarketStatusBar({
  data,
  remainingMs,
  countdownTarget,
  updatedRelative,
}: MarketStatusBarProps) {
  if (!data) {
    return (
      <section className="market-bar market-bar--skeleton" aria-label="시장 상태">
        <span className="market-bar__badge market-bar__badge--closed">—</span>
      </section>
    );
  }

  const showsStaleData = data.status === "holiday" || data.status === "pre";
  const countdownText =
    remainingMs !== null && countdownTarget
      ? `${countdownTarget === "close" ? "마감" : "개장"}까지 ${formatRemaining(remainingMs)}`
      : null;

  return (
    <section className="market-bar" aria-label="시장 상태">
      <span className={`market-bar__badge ${STATUS_CLASS[data.status]}`}>{data.label}</span>

      <div className="market-bar__detail">
        {countdownText ? (
          <span className="market-bar__countdown">
            {countdownText}
            {countdownTarget === "open" && data.session_date !== data.reference_trading_day
              ? ` (${formatMonthDay(data.session_date)})`
              : null}
          </span>
        ) : null}

        {showsStaleData ? (
          <span className="market-bar__reference">
            {formatMonthDay(data.reference_trading_day)} 거래일 기준
          </span>
        ) : null}

        <span className="market-bar__updated">갱신 {updatedRelative || "방금"}</span>
      </div>

      {/* 휴장일 표가 없는 연도에서는 음력 연휴를 놓칠 수 있다 → 단정하지 않는다. */}
      {!data.calendar_covered ? (
        <p className="market-bar__caveat">
          이 연도의 휴장일 정보가 없어 공휴일 판정이 정확하지 않을 수 있습니다.
        </p>
      ) : null}
    </section>
  );
}
