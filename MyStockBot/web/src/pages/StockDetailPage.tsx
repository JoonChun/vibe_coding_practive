import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { BollingerTrack } from "../components/BollingerTrack";
import { CandleChart } from "../components/CandleChart";
import { DecisionGauge } from "../components/DecisionGauge";
import { FactorBreakdown } from "../components/FactorBreakdown";
import { LiveReferenceStrip } from "../components/LiveReferenceStrip";
import { RealtimeBadge } from "../components/RealtimeBadge";
import { TokenBanner } from "../components/TokenBanner";
import { useRelativeTime } from "../hooks/useRelativeTime";
import { useSnapshot } from "../hooks/useSnapshot";
import { useTickFlash, type TickFlashDirection } from "../hooks/useTickFlash";
import { useTickStream } from "../hooks/useTickStream";
import { buildFactorRows, sumFactorScores } from "../utils/factorScoring";

type AnalysisTab = "short" | "long";

const TAB_LABEL: Record<AnalysisTab, string> = {
  short: "단기 · 60분봉",
  long: "장기 · 일봉+재무",
};

const TAB_THRESHOLD: Record<AnalysisTab, number> = {
  short: 2,
  long: 3,
};

/**
 * 종목 상세 판정 페이지 — /stocks/:code
 * 스냅샷은 대시보드와 동일한 useSnapshot 폴링(20초)을 재사용해 코드로 필터링하고,
 * 캔들 차트는 CandleChart가 자체적으로 /api/stocks/{code}/candles 를 타임프레임별로 조회한다.
 */
export default function StockDetailPage() {
  const { code: codeParam } = useParams<{ code: string }>();
  const code = codeParam ?? "";
  const navigate = useNavigate();
  const [tab, setTab] = useState<AnalysisTab>("short");

  const snapshot = useSnapshot();
  const relativeUpdatedAt = useRelativeTime(snapshot.lastUpdatedAt);
  const tickStream = useTickStream();
  const tick = tickStream.ticks[code] ?? null;

  const item = useMemo(
    () => snapshot.data?.items.find((i) => i.code === code) ?? null,
    [snapshot.data, code]
  );

  const view = tab === "short" ? (item?.short_view ?? null) : (item?.long_view ?? null);
  const otherView = tab === "short" ? (item?.long_view ?? null) : (item?.short_view ?? null);
  const threshold = TAB_THRESHOLD[tab];
  const liveKind = tab === "short" ? "단기" : "장기";
  const wsConnected = tickStream.connected && tickStream.kisConnected;

  const factorRows = useMemo(
    () => (item?.factors ? buildFactorRows(item.factors, tab) : null),
    [item, tab]
  );
  const score = factorRows ? sumFactorScores(factorRows) : null;

  // 틱이 있으면 스냅샷 대신 실시간 값을 표시(무틱 시 기존 스냅샷 값 그대로)
  const close = tick ? tick.price : (item?.close ?? null);
  const change = tick ? tick.change : (item?.change ?? null);
  const changePct = tick ? tick.changePct : (item?.change_pct ?? null);
  const isUp = change !== null && change > 0;
  const isDown = change !== null && change < 0;
  const changeDirection = isUp ? "up" : isDown ? "down" : "flat";

  const flashDirection: TickFlashDirection = !tick
    ? null
    : tick.change > 0
      ? "up"
      : tick.change < 0
        ? "down"
        : null;
  const flashClass = useTickFlash(flashDirection, tick?.receivedAt);
  const changeText =
    change === null || changePct === null
      ? "—"
      : `${change > 0 ? "+" : ""}${change.toLocaleString("ko-KR")} (${
          changePct > 0 ? "+" : ""
        }${changePct.toFixed(2)}%)`;
  const changeAriaLabel =
    change === null || changePct === null
      ? "등락 정보 없음"
      : `전일 대비 ${isUp ? "상승" : isDown ? "하락" : "보합"} ${Math.abs(change).toLocaleString(
          "ko-KR"
        )}원, ${Math.abs(changePct).toFixed(2)}퍼센트`;

  const unauthorized = snapshot.errorStatus === 401;
  const showConnectionBanner = !unauthorized && Boolean(snapshot.error) && !snapshot.data;

  const name = item?.name ?? code;

  return (
    <div className="app">
      {unauthorized ? (
        <TokenBanner onSaved={() => snapshot.refresh()} />
      ) : showConnectionBanner ? (
        <div className="banner banner--error" role="alert">
          서버에 연결할 수 없습니다
        </div>
      ) : null}

      <header className="detail-header">
        <button
          type="button"
          className="detail-header__back"
          onClick={() => navigate(-1)}
          aria-label="뒤로가기"
        >
          <span aria-hidden="true">←</span>
        </button>
        <div className="detail-header__title">
          <h1 className="detail-header__name">{name}</h1>
          <span className="detail-header__meta">{code} KRX</span>
        </div>
        <RealtimeBadge live={wsConnected} />
      </header>

      <main className="dash-main detail-main">
        {!item ? (
          <p className="watchlist-empty">
            관심종목에 등록되지 않았거나 스냅샷 데이터가 아직 없습니다.
          </p>
        ) : null}

        <section className="price-section">
          <div className="price-section__main">
            <div
              className={`price-section__row${flashClass ? ` ${flashClass}` : ""}`}
            >
              <span className="price-section__value">
                {close !== null ? `${close.toLocaleString("ko-KR")}원` : "—"}
              </span>
              <span
                className={`price-section__change price-section__change--${changeDirection}`}
                aria-label={changeAriaLabel}
              >
                <span aria-hidden="true">{isUp ? "▲" : isDown ? "▼" : ""}</span> {changeText}
              </span>
            </div>
            <div className="price-section__updated">
              <span className="price-section__updated-dot" aria-hidden="true" />
              <span>갱신 · {snapshot.lastUpdatedAt ? relativeUpdatedAt : "정보 없음"}</span>
            </div>
          </div>

          <div className="analysis-toggle-wrap">
            <div className="analysis-toggle" role="tablist" aria-label="분석 관점 선택">
              {(Object.keys(TAB_LABEL) as AnalysisTab[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={tab === key}
                  className={`analysis-toggle__btn${
                    tab === key ? " analysis-toggle__btn--active" : ""
                  }`}
                  onClick={() => setTab(key)}
                >
                  {TAB_LABEL[key]}
                </button>
              ))}
            </div>
            {item ? (
              <button
                type="button"
                className="analysis-toggle__peek"
                onClick={() => setTab(tab === "short" ? "long" : "short")}
              >
                {tab === "short" ? "장기" : "단기"}: {otherView ?? "데이터부족"}
                <span aria-hidden="true"> ›</span>
              </button>
            ) : null}
          </div>
        </section>

        <div className="detail-grid">
          <div className="detail-grid__gauge">
            <DecisionGauge
              view={view}
              score={score}
              threshold={threshold}
              relativeTime={relativeUpdatedAt || "방금"}
              liveStrip={
                <LiveReferenceStrip
                  variant="full"
                  kind={liveKind}
                  live={item?.live ?? null}
                  confirmedView={view}
                  wsConnected={wsConnected}
                />
              }
            />
          </div>
          <div className="detail-grid__factors">
            <FactorBreakdown rows={factorRows} />
          </div>
          <div className="detail-grid__bollinger">
            <BollingerTrack
              upper={item?.factors?.bb_upper ?? null}
              mid={item?.factors?.bb_mid ?? null}
              lower={item?.factors?.bb_lower ?? null}
              price={close}
            />
          </div>
          <div className="detail-grid__chart">
            <CandleChart
              code={code}
              liveBars={tickStream.liveBars[code]}
              wsConnected={wsConnected}
            />
          </div>
        </div>
      </main>

      <footer className="app-footer">
        ⓘ 기계적 참고 지표 · 투자 권유 아님 · 최종 판단은 본인에게 있습니다
      </footer>
    </div>
  );
}
