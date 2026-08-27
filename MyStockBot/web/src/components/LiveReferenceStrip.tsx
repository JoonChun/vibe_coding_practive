import { useMemo, type ReactNode } from "react";
import { useRelativeTime } from "../hooks/useRelativeTime";
import type { LiveJudgment, SignalView } from "../types";
import { SignalChip } from "./SignalChip";

interface LiveReferenceStripProps {
  /** compact = StockCard 목록(3절), full = 상세 페이지 게이지 아래(4절) */
  variant: "compact" | "full";
  /** "단기" | "장기" — 이 kind에 대응하는 live 필드만 골라 쓴다 */
  kind: "단기" | "장기";
  live: LiveJudgment | null;
  /** 확정 판정(short_view/long_view 중 이 kind에 해당하는 값) — "다름" 판정 기준 */
  confirmedView: SignalView | null;
  /** tickStream.connected && tickStream.kisConnected — RealtimeBadge와 동일 신호(워밍업/미가용 구분용 보조 신호) */
  wsConnected: boolean;
  /**
   * 확정 판정이 워밍업 구간인지(60분봉 35봉 미만). 확정이 '축적 중'인데 실시간만
   * '관망'을 띄우면 같은 화면에서 두 값이 모순돼 보인다 — 그때는 실시간도 함께
   * '축적 중'으로 표시한다(단기 관점에만 해당).
   */
  warming?: boolean;
}

type LiveStripState = "fresh" | "stale" | "warming_up" | "unavailable";

// 스냅샷 폴링(20초)의 6주기 분량 — 실측 후 조정 가능(docs/wireframes/phase2v2-live-ui.md §2)
const STALE_THRESHOLD_MS = 120_000;

// SignalChip.tsx CHIP_STYLES·DecisionGauge.tsx VIEW_COLORS와 동일한 5단계 팔레트 재사용(신규 색 없음)
const VIEW_COLORS: Record<string, string> = {
  강력매도: "#7f1d1d",
  매도: "#dc2626",
  관망: "#6b7280",
  매수: "#65a30d",
  강력매수: "#15803d",
};

function computeRawState(live: LiveJudgment | null, wsConnected: boolean): LiveStripState {
  if (live !== null && live.updated_at) {
    const updatedMs = new Date(live.updated_at).getTime();
    if (Number.isFinite(updatedMs)) {
      return Date.now() - updatedMs <= STALE_THRESHOLD_MS ? "fresh" : "stale";
    }
  }
  return wsConnected ? "warming_up" : "unavailable";
}

function formatScore(score: number | null): string {
  if (score === null) return "—";
  return `${score > 0 ? "+" : ""}${score}`;
}

/**
 * "확정 판정 vs 실시간 참고 판정" 4-state(fresh/stale/warming_up/unavailable) 판정 로직을
 * 한 곳에 캡슐화 — StockCard(compact)·StockDetailPage(full) 양쪽에서 재사용해
 * 두 화면이 서로 다르게 구현되는 것을 방지한다. 확정 판정을 절대 압도하지 않도록
 * 배경은 항상 transparent, outline/텍스트에만 VIEW_COLORS를 쓴다.
 */
export function LiveReferenceStrip({
  variant,
  kind,
  live,
  confirmedView,
  wsConnected,
  warming = false,
}: LiveReferenceStripProps) {
  const viewLive = kind === "단기" ? (live?.short_view_live ?? null) : (live?.long_view_live ?? null);
  const scoreLive =
    kind === "단기" ? (live?.short_score_live ?? null) : (live?.long_score_live ?? null);

  const updatedAtDate = useMemo(
    () => (live?.updated_at ? new Date(live.updated_at) : null),
    [live?.updated_at]
  );
  const relativeTime = useRelativeTime(updatedAtDate);

  const rawState = computeRawState(live, wsConnected);
  // live 객체 자체는 fresh인데 이 kind의 값만 아직 없는 방어적 예외 상황 — 준비 중으로 격하
  const state: LiveStripState = rawState === "fresh" && viewLive === null ? "warming_up" : rawState;

  if (variant === "compact") {
    if (state !== "fresh" || viewLive === confirmedView) return null;
    const ariaLabel = `${kind} 관점 실시간 참고: ${viewLive}로 전환 조짐, 확정 판정은 ${
      confirmedView ?? "데이터부족"
    }`;
    return (
      <span className="live-strip live-strip--compact" aria-label={ariaLabel}>
        <span className="live-strip__dot" aria-hidden="true" />
        <span className="live-strip__value" aria-hidden="true">
          LIVE {kind}:
        </span>
        <span aria-hidden="true">
          <SignalChip label={viewLive} kind={kind} variant="live" warming={warming} />
        </span>
      </span>
    );
  }

  // full
  if (state === "unavailable") return null;

  let valueNode: ReactNode;
  let captionText: string | null;
  let pulsing = false;

  if (state === "fresh") {
    pulsing = true;
    const color = VIEW_COLORS[viewLive as string] ?? "#6b7280";
    valueNode = (
      <span className="live-strip__value" style={{ color }}>
        LIVE 참고 · {viewLive} ({formatScore(scoreLive)})
      </span>
    );
    captionText =
      viewLive !== confirmedView ? `확정과 다름 · ${relativeTime} 갱신` : `${relativeTime} 갱신`;
  } else if (state === "stale") {
    valueNode = <span className="live-strip__value">LIVE 참고 판정 지연 중</span>;
    captionText = `마지막 갱신 ${relativeTime}`;
  } else {
    valueNode = <span className="live-strip__value">LIVE 참고 판정 준비 중…</span>;
    captionText = null;
  }

  return (
    <div className="gauge-card__divider">
      <div className="live-strip live-strip--full">
        <span
          className={`live-strip__dot${pulsing ? " live-strip__dot--pulse" : ""}`}
          aria-hidden="true"
        />
        {valueNode}
      </div>
      {captionText ? <p className="live-strip__caption">{captionText}</p> : null}
    </div>
  );
}
