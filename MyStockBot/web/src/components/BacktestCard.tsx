import { useState } from "react";
import { ApiError, getBacktest } from "../api";
import type { BacktestResponse } from "../types";

/** 두 계열(전략 vs 보유) 누적수익률 곡선을 SVG 폴리라인으로 그린다. */
function MiniCurve({ data }: { data: BacktestResponse["curve"] }) {
  if (data.length < 2) return null;
  const W = 300;
  const H = 96;
  const xs = data.map((_, i) => (i / (data.length - 1)) * W);
  const all = data.flatMap((d) => [d.strategy, d.buyhold]);
  const min = Math.min(...all, 0);
  const max = Math.max(...all, 0);
  const span = max - min || 1;
  const y = (v: number) => H - ((v - min) / span) * H;
  const line = (key: "strategy" | "buyhold") =>
    data.map((d, i) => `${xs[i].toFixed(1)},${y(d[key]).toFixed(1)}`).join(" ");
  const zeroY = y(0);

  return (
    <svg
      className="bt-curve"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="전략 vs 단순보유 누적수익률"
    >
      <line x1="0" y1={zeroY} x2={W} y2={zeroY} className="bt-curve__zero" />
      <polyline points={line("buyhold")} className="bt-curve__buyhold" fill="none" />
      <polyline points={line("strategy")} className="bt-curve__strategy" fill="none" />
    </svg>
  );
}

const pct = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;

/**
 * 판정 백테스트 카드 — "이 앱 판정대로 샀으면?"
 * 무거운 계산이라 버튼으로 온디맨드 실행. 매수 판정 적중률·평균 선행수익률과
 * 판정 따라가기 vs 단순보유 누적수익률을 보여준다.
 */
export function BacktestCard({ code }: { code: string }) {
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      setData(await getBacktest(code, 20));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "백테스트에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card bt-card" aria-label="판정 백테스트">
      <div className="bt-card__head">
        <h3 className="bt-card__title">판정 백테스트</h3>
        <span className="bt-card__sub">이 앱 판정대로 샀다면?</span>
      </div>

      {!data ? (
        <div className="bt-card__cta">
          <button type="button" className="bt-run" onClick={() => void run()} disabled={loading}>
            {loading ? "계산 중…" : "백테스트 실행"}
          </button>
          {error ? (
            <p className="panel__error" role="alert">
              {error}
            </p>
          ) : (
            <p className="bt-card__hint">
              과거 각 시점에 기술적 판정을 재적용해 적중률·가상수익률을 계산합니다.
            </p>
          )}
        </div>
      ) : (
        <div className="bt-card__body">
          <div className="bt-stats">
            <div className="bt-stat">
              <span className="bt-stat__k">매수 판정 적중률</span>
              <span className="bt-stat__v">
                {data.buy.hit_rate === null ? "—" : `${data.buy.hit_rate.toFixed(1)}%`}
              </span>
              <span className="bt-stat__sub">{data.buy.signals}회 · {data.horizon_days}일 뒤 기준</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">매수 후 평균수익</span>
              <span className={`bt-stat__v ${(data.buy.avg_forward_pct ?? 0) >= 0 ? "index-card__chg--up" : "index-card__chg--down"}`}>
                {pct(data.buy.avg_forward_pct)}
              </span>
              <span className="bt-stat__sub">{data.horizon_days}거래일 선행</span>
            </div>
          </div>

          <MiniCurve data={data.curve} />
          <div className="bt-legend">
            <span className="bt-legend__item">
              <i className="bt-legend__swatch bt-legend__swatch--strategy" /> 판정 따라가기{" "}
              <b className={data.strategy_return_pct >= 0 ? "index-card__chg--up" : "index-card__chg--down"}>
                {pct(data.strategy_return_pct)}
              </b>
            </span>
            <span className="bt-legend__item">
              <i className="bt-legend__swatch bt-legend__swatch--buyhold" /> 단순 보유{" "}
              <b className={data.buy_hold_return_pct >= 0 ? "index-card__chg--up" : "index-card__chg--down"}>
                {pct(data.buy_hold_return_pct)}
              </b>
            </span>
          </div>

          <p className="bt-card__disc">
            {data.start_date && data.end_date
              ? `${data.start_date} ~ ${data.end_date} · `
              : ""}
            과거 성과는 미래를 보장하지 않으며 수수료·슬리피지 미반영, 기술적 판정만
            사용합니다.
          </p>
        </div>
      )}
    </section>
  );
}
