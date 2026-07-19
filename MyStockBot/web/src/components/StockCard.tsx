import { useState, type MouseEvent } from "react";
import { Link } from "react-router-dom";
import type { TickData } from "../hooks/useTickStream";
import { useTickFlash, type TickFlashDirection } from "../hooks/useTickFlash";
import type { LiveJudgment, SignalView, SnapshotSource } from "../types";
import { LiveReferenceStrip } from "./LiveReferenceStrip";
import { SignalChip } from "./SignalChip";
import { SourceBadge } from "./SourceBadge";
import { Sparkline } from "./Sparkline";

export interface StockCardData {
  code: string;
  name: string;
  close: number | null;
  changePct: number | null;
  shortView: SignalView | null;
  longView: SignalView | null;
  source: SnapshotSource | null;
  market?: string | null;
  /** 실시간 참고 판정(additive) — 확정과 다를 때만 카드에 조용히 노출 */
  live?: LiveJudgment | null;
}

interface StockCardProps {
  row: StockCardData;
  onDelete: (code: string) => Promise<void>;
  /** 실시간 틱 — 있으면 가격·등락률을 이 값으로 표시하고 수신 순간 300ms 플래시 */
  tick?: TickData | null;
  /** tickStream.connected && tickStream.kisConnected — LiveReferenceStrip의 워밍업/미가용 판정 보조 신호 */
  wsConnected: boolean;
}

const MARKET_BADGE_CLASS: Record<string, string> = {
  KOSPI: "market-badge market-badge--kospi",
  KOSDAQ: "market-badge market-badge--kosdaq",
};

export function StockCard({ row, onDelete, tick, wsConnected }: StockCardProps) {
  const [pending, setPending] = useState(false);
  const { code, name, shortView, longView, source, market } = row;
  const marketLabel = market ?? "KRX";
  const marketBadgeClass = MARKET_BADGE_CLASS[marketLabel] ?? "market-badge";

  // 틱이 있으면 스냅샷 대신 실시간 값을 표시(무틱 시 기존 스냅샷 값 그대로)
  const close = tick ? tick.price : row.close;
  const changePct = tick ? tick.changePct : row.changePct;

  const flashDirection: TickFlashDirection = !tick
    ? null
    : tick.change > 0
      ? "up"
      : tick.change < 0
        ? "down"
        : null;
  const flashClass = useTickFlash(flashDirection, tick?.receivedAt);

  const isUp = changePct !== null && changePct > 0;
  const isDown = changePct !== null && changePct < 0;
  const changeText =
    changePct === null
      ? "—"
      : `${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%`;
  const changeClass = isUp
    ? "stock-card__change--up"
    : isDown
      ? "stock-card__change--down"
      : "stock-card__change--flat";
  const changeAriaLabel =
    changePct === null
      ? "등락률 정보 없음"
      : `등락률 ${isUp ? "상승" : isDown ? "하락" : "보합"} ${Math.abs(changePct).toFixed(2)}퍼센트`;

  async function handleDeleteClick(e: MouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    e.stopPropagation();
    const confirmed = window.confirm(
      `${name} (${code}) 종목을 관심종목에서 삭제할까요?`
    );
    if (!confirmed) return;

    setPending(true);
    try {
      await onDelete(code);
    } finally {
      setPending(false);
    }
  }

  return (
    <li
      className={`stock-card${flashClass ? ` ${flashClass}` : ""}`}
      id={`stock-card-${code}`}
    >
      <button
        type="button"
        className="stock-card__delete"
        aria-label={`${name} (${code}) 관심종목에서 삭제`}
        onClick={(e) => void handleDeleteClick(e)}
        disabled={pending}
      >
        <span aria-hidden="true">×</span>
      </button>
      <Link
        to={`/stocks/${code}`}
        className="stock-card__link"
        aria-label={`${name} (${code}) 상세 보기`}
      >
        <div className="stock-card__head">
          <span className="stock-card__name">{name}</span>
          <span className={marketBadgeClass}>{marketLabel}</span>
        </div>
        <span className="stock-card__code">{code}</span>

        <div className="stock-card__price-row">
          <span className="stock-card__price">
            {close !== null ? `${close.toLocaleString("ko-KR")}원` : "—"}
          </span>
          <span className={`stock-card__change ${changeClass}`} aria-label={changeAriaLabel}>
            <span aria-hidden="true">
              {isUp ? "▲ " : isDown ? "▼ " : ""}
              {changeText}
            </span>
          </span>
        </div>

        <Sparkline code={code} trendUp={isUp} trendDown={isDown} />

        <div className="stock-card__chips">
          <SignalChip label={shortView} kind="단기" />
          <SignalChip label={longView} kind="장기" />
        </div>

        <div className="stock-card__live-row">
          <LiveReferenceStrip
            variant="compact"
            kind="단기"
            live={row.live ?? null}
            confirmedView={shortView}
            wsConnected={wsConnected}
          />
          <LiveReferenceStrip
            variant="compact"
            kind="장기"
            live={row.live ?? null}
            confirmedView={longView}
            wsConnected={wsConnected}
          />
        </div>

        <SourceBadge source={source} />
      </Link>
    </li>
  );
}
