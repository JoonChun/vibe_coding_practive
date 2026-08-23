import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { BacktestCard } from "../components/BacktestCard";
import { DcaCard } from "../components/DcaCard";
import { BollingerTrack } from "../components/BollingerTrack";
import { CandleChart } from "../components/CandleChart";
import { DecisionGauge } from "../components/DecisionGauge";
import { FactorBreakdown } from "../components/FactorBreakdown";
import { PullbackCard } from "../components/PullbackCard";
import { RealtimeBadge } from "../components/RealtimeBadge";
import { TokenBanner } from "../components/TokenBanner";
import { useRelativeTime } from "../hooks/useRelativeTime";
import { useSnapshot } from "../hooks/useSnapshot";
import { useTickFlash, type TickFlashDirection } from "../hooks/useTickFlash";
import { useTickStream } from "../hooks/useTickStream";
import type { DecisionRules } from "../types";
import { isShortViewWarming } from "../utils/decision";

type AnalysisTab = "short" | "long";

const TAB_LABEL: Record<AnalysisTab, string> = {
  short: "단기 · 60분봉",
  long: "장기 · 일봉+재무",
};

/**
 * 백엔드가 rules 를 내려주지 않을 때(구버전 서버)만 쓰는 폴백.
 * 임계값을 프론트에 복제해 두면 백엔드 규칙이 바뀔 때 조용히 어긋나므로, 평소에는
 * 응답의 rules 를 그대로 쓴다.
 */
const FALLBACK_RULES: DecisionRules = {
  weak: 1,
  short_strong: 2,
  long_strong: 3,
  long_strong_requires_tech_confirm: true,
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

  // 판정 규칙·기여요인·점수 전부 백엔드 값을 그대로 쓴다(화면에서 재계산하지 않는다).
  const rules = snapshot.data?.rules ?? FALLBACK_RULES;
  const threshold = tab === "short" ? rules.short_strong : rules.long_strong;

  const factorRows = useMemo(() => {
    if (!item?.factors) return null;
    return tab === "short"
      ? item.factors.breakdown_short
      : item.factors.breakdown_long;
  }, [item, tab]);
  const score =
    tab === "short"
      ? (item?.factors?.short_score ?? null)
      : (item?.factors?.long_score ?? null);

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
        <RealtimeBadge live={tickStream.connected && tickStream.kisConnected} />
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
          {item ? (
            <>
              <div className="detail-grid__gauge">
                <DecisionGauge
                  view={view}
                  score={score}
                  threshold={threshold}
                  weak={rules.weak}
                  relativeTime={relativeUpdatedAt || "방금"}
                  warming={tab === "short" && isShortViewWarming(item?.factors)}
                />
              </div>
              <div className="detail-grid__factors">
                <FactorBreakdown rows={factorRows} rules={rules} view={tab} />
                {/* 눌림목은 일봉 기반이라 장기 탭에서만 의미가 있다 */}
                {tab === "long" ? (
                  <PullbackCard
                    status={item?.factors?.pullback_status ?? null}
                    reason={item?.factors?.pullback_reason ?? null}
                    checks={item?.factors?.pullback_checks}
                  />
                ) : null}
              </div>
              <div className="detail-grid__bollinger">
                <BollingerTrack
                  upper={item?.factors?.bb_upper ?? null}
                  mid={item?.factors?.bb_mid ?? null}
                  lower={item?.factors?.bb_lower ?? null}
                  price={close}
                />
              </div>
            </>
          ) : (
            <div className="detail-grid__cta">
              <p>
                이 종목은 아직 관심종목이 아니라 판정·팩터 분석 데이터가 없습니다.
                관심종목에 추가하면 매수/매도 판정과 기여요인을 볼 수 있어요.
                아래 차트와 백테스트는 지금도 확인할 수 있습니다.
              </p>
            </div>
          )}
          <div className="detail-grid__chart">
            <CandleChart code={code} />
          </div>
        </div>

        <BacktestCard code={code} />
        <DcaCard code={code} name={name} />
      </main>

      <footer className="app-footer">
        ⓘ 기계적 참고 지표 · 투자 권유 아님 · 최종 판단은 본인에게 있습니다
      </footer>
    </div>
  );
}
