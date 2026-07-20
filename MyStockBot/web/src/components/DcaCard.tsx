import { useState } from "react";
import { ApiError, getDca } from "../api";
import type { DcaResponse } from "../types";

const won = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `${Math.round(n).toLocaleString("ko-KR")}원`;

/** 평가금액(면적) vs 누적 원금(점선) 미니 차트. */
function DcaCurve({ data }: { data: DcaResponse["curve"] }) {
  if (data.length < 2) return null;
  const W = 300;
  const H = 90;
  const max = Math.max(...data.map((d) => Math.max(d.value, d.principal)), 1);
  const x = (i: number) => (i / (data.length - 1)) * W;
  const y = (v: number) => H - (v / max) * H;
  const valLine = data.map((d, i) => `${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join(" ");
  const priLine = data.map((d, i) => `${x(i).toFixed(1)},${y(d.principal).toFixed(1)}`).join(" ");
  const area = `0,${H} ${valLine} ${W},${H}`;

  return (
    <svg className="dca-curve" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label="평가금액 대 누적원금">
      <polygon points={area} className="dca-curve__fill" />
      <polyline points={priLine} className="dca-curve__principal" fill="none" />
      <polyline points={valLine} className="dca-curve__value" fill="none" />
    </svg>
  );
}

const YEARS = [
  { label: "3년", months: 36 },
  { label: "5년", months: 60 },
  { label: "10년", months: 120 },
];

/**
 * 적립식 백테스트 카드 — "매달 N주씩 샀다면 지금 얼마?"
 * 정량(매월 주수) 기준, 기간(3/5/10년) 선택. 온디맨드 실행.
 */
export function DcaCard({ code }: { code: string }) {
  const [months, setMonths] = useState(120);
  const [qty, setQty] = useState("1");
  const [data, setData] = useState<DcaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(m: number) {
    setMonths(m);
    setLoading(true);
    setError(null);
    const per = Math.max(1, Number(qty) || 1);
    try {
      setData(await getDca(code, { mode: "qty", per, months: m }));
    } catch (e) {
      setData(null);
      setError(e instanceof ApiError ? e.message : "적립식 백테스트에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  const up = (data?.return_pct ?? 0) >= 0;

  return (
    <section className="card bt-card" aria-label="적립식 백테스트">
      <div className="bt-card__head">
        <h3 className="bt-card__title">적립식 백테스트</h3>
        <span className="bt-card__sub">매달 사왔다면 지금 얼마?</span>
      </div>

      <div className="dca-controls">
        <label className="dca-qty">
          <span>매월</span>
          <input inputMode="numeric" value={qty} onChange={(e) => setQty(e.target.value)} />
          <span>주씩</span>
        </label>
        <div className="dca-years">
          {YEARS.map((y) => (
            <button
              key={y.months}
              type="button"
              className={"dca-year" + (months === y.months && data ? " dca-year--on" : "")}
              disabled={loading}
              onClick={() => void run(y.months)}
            >
              {y.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="bt-card__hint">계산 중…</p>
      ) : error ? (
        <p className="panel__error" role="alert">
          {error}
        </p>
      ) : data ? (
        <div className="bt-card__body">
          <div className="dca-result">
            <span className={`dca-result__pct ${up ? "index-card__chg--up" : "index-card__chg--down"}`}>
              {up ? "+" : ""}
              {data.return_pct.toFixed(2)}%
            </span>
            <span className="dca-result__lab">누적 수익률 · {data.buys}회 매수</span>
          </div>
          <div className="bt-stats">
            <div className="bt-stat">
              <span className="bt-stat__k">투자 원금</span>
              <span className="bt-stat__v">{won(data.principal)}</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">평가금액</span>
              <span className="bt-stat__v">{won(data.eval_value)}</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">수익</span>
              <span className={`bt-stat__v ${up ? "index-card__chg--up" : "index-card__chg--down"}`}>
                {data.profit >= 0 ? "+" : ""}
                {won(data.profit)}
              </span>
            </div>
          </div>
          <DcaCurve data={data.curve} />
          <div className="bt-legend">
            <span className="bt-legend__item">
              <i className="bt-legend__swatch bt-legend__swatch--strategy" /> 평가금액
            </span>
            <span className="bt-legend__item">
              <i className="bt-legend__swatch bt-legend__swatch--buyhold" /> 누적 원금
            </span>
          </div>
          <p className="bt-card__disc">
            {data.start_date && data.end_date ? `${data.start_date} ~ ${data.end_date} · ` : ""}
            수수료·세금·배당·환율 미반영. 과거 성과는 미래를 보장하지 않습니다.
          </p>
        </div>
      ) : (
        <p className="bt-card__hint">기간을 선택하면 매월 정기 매수 결과를 계산합니다.</p>
      )}
    </section>
  );
}
