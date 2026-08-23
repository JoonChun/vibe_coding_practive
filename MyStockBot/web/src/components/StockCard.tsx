import { useState, type MouseEvent } from "react";
import { Link } from "react-router-dom";
import type { TickData } from "../hooks/useTickStream";
import { useTickFlash, type TickFlashDirection } from "../hooks/useTickFlash";
import type { SignalView, SnapshotSource } from "../types";
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
  /** 60분봉이 아직 35개 미만 — 단기 판정을 신뢰할 수 없는 구간 */
  shortWarming?: boolean;
  /** KIS 구독 한도(41건)에 걸려 실시간 시세에서 제외된 종목 */
  realtimeExcluded?: boolean;
}

interface StockCardProps {
  row: StockCardData;
  onDelete: (code: string) => Promise<void>;
  /** 실시간 틱 — 있으면 가격·등락률을 이 값으로 표시하고 수신 순간 300ms 플래시 */
  tick?: TickData | null;
}

const MARKET_BADGE_CLASS: Record<string, string> = {
  KOSPI: "market-badge market-badge--kospi",
  KOSDAQ: "market-badge market-badge--kosdaq",
};

export function StockCard({ row, onDelete, tick }: StockCardProps) {
  const [pending, setPending] = useState(false);
  const { code, name, shortView, longView, source, market, shortWarming, realtimeExcluded } = row;
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
    // 네이티브 confirm 대신 낙관적 삭제 + '실행 취소' 토스트(부모에서 처리)
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
          <SignalChip label={shortView} kind="단기" warming={shortWarming} />
          <SignalChip label={longView} kind="장기" />
        </div>

        <div className="stock-card__badges">
          <SourceBadge source={source} />
          {realtimeExcluded ? (
            <span
              className="source-badge source-badge--yfinance"
              title="KIS 세션 구독 한도(41건)를 넘어 실시간 시세에서 제외된 종목입니다 — 판정·종가는 정상 수집됩니다"
            >
              실시간 제외
            </span>
          ) : null}
        </div>
      </Link>
    </li>
  );
}
