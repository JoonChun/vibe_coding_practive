import { useEffect, useRef, useState } from "react";
import { ApiError, getDca } from "../api";
import type { DcaResponse } from "../types";

/** 큰 금액 축약(억/만) — 좁은 카드 셀 넘침 방지. */
const wonC = (n: number): string => {
  const a = Math.abs(Math.round(n));
  const s = n < 0 ? "-" : "";
  if (a >= 1e8) return `${s}${a / 1e8 >= 10 ? (a / 1e8).toFixed(1) : (a / 1e8).toFixed(2)}억`;
  if (a >= 1e4) return `${s}${Math.round(a / 1e4).toLocaleString("ko-KR")}만`;
  return `${s}${a.toLocaleString("ko-KR")}`;
};

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

type Mode = "qty" | "amount";
type Freq = "weekly" | "monthly" | "quarterly";

const YEARS = [
  { label: "3년", months: 36 },
  { label: "5년", months: 60 },
  { label: "10년", months: 120 },
];
const FREQS: { v: Freq; label: string }[] = [
  { v: "weekly", label: "매주" },
  { v: "monthly", label: "매월" },
  { v: "quarterly", label: "매분기" },
];
const FREQ_WORD: Record<Freq, string> = { weekly: "매주", monthly: "매월", quarterly: "매분기" };

/**
 * 적립식 백테스트 카드 — "그때부터 매주/매월/매분기 사왔다면 지금 얼마?"
 * 정량(주수)/정액(금액)·주기·기간·배당 재투자 선택. 최초 실행 후 컨트롤 변경 시 자동 재계산.
 * (배당 재투자는 백엔드 미연동이라 응답 notes 로 미반영을 고지한다.)
 */
export function DcaCard({ code }: { code: string }) {
  const [mode, setMode] = useState<Mode>("qty");
  const [per, setPer] = useState("1");
  const [months, setMonths] = useState(120);
  const [freq, setFreq] = useState<Freq>("monthly");
  const [reinvest, setReinvest] = useState(false);
  const [data, setData] = useState<DcaResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasRun = useRef(false);

  async function run(
    override: Partial<{ mode: Mode; per: number; months: number; freq: Freq; reinvest: boolean }> = {}
  ) {
    hasRun.current = true;
    setLoading(true);
    setError(null);
    const q = {
      mode,
      per: Math.max(1, Number(per) || 1),
      months,
      freq,
      reinvest,
      ...override,
    };
    try {
      setData(await getDca(code, q));
    } catch (e) {
      setData(null);
      setError(e instanceof ApiError ? e.message : "적립식 백테스트에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  // 최초 실행 이후에는 방식/금액/주기/배당 변경 시 자동 재계산(디바운스). 기간은 버튼이 직접 실행.
  useEffect(() => {
    if (!hasRun.current) return;
    const id = window.setTimeout(() => void run(), 350);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, per, freq, reinvest]);

  function toggleMode(m: Mode) {
    if (m === mode) return;
    setMode(m);
    setPer(m === "qty" ? "1" : "100000"); // 방식 전환 시 합리적 기본값
  }

  const up = (data?.return_pct ?? 0) >= 0;
  const perUnit = mode === "qty" ? "주씩" : "원씩";

  return (
    <section className="card bt-card" aria-label="적립식 백테스트">
      <div className="bt-card__head">
        <h3 className="bt-card__title">그때부터 모았다면</h3>
        <span className="bt-card__sub">그때부터 사왔다면 지금 얼마? · 적립식 백테스트</span>
      </div>

      <div className="dca-controls">
        <div className="dca-seg" role="tablist" aria-label="매수 방식">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "qty"}
            className={"dca-seg__btn" + (mode === "qty" ? " dca-seg__btn--on" : "")}
            onClick={() => toggleMode("qty")}
          >
            정량 (주)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "amount"}
            className={"dca-seg__btn" + (mode === "amount" ? " dca-seg__btn--on" : "")}
            onClick={() => toggleMode("amount")}
          >
            정액 (원)
          </button>
        </div>

        <div className="dca-row">
          <label className="dca-qty">
            <span>{FREQ_WORD[freq]}</span>
            <input
              inputMode="numeric"
              value={per}
              onChange={(e) => setPer(e.target.value)}
              aria-label={`회당 매수 ${mode === "qty" ? "주수" : "금액"}`}
            />
            <span>{perUnit}</span>
          </label>
          <label className="dca-select">
            <span className="sr-only">매수 주기</span>
            <select value={freq} onChange={(e) => setFreq(e.target.value as Freq)} aria-label="매수 주기">
              {FREQS.map((f) => (
                <option key={f.v} value={f.v}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="dca-row">
          <div className="dca-years">
            {YEARS.map((y) => (
              <button
                key={y.months}
                type="button"
                className={"dca-year" + (months === y.months && data ? " dca-year--on" : "")}
                disabled={loading}
                onClick={() => {
                  setMonths(y.months);
                  void run({ months: y.months });
                }}
              >
                {y.label}
              </button>
            ))}
          </div>
          <label className="dca-reinvest">
            <input
              type="checkbox"
              checked={reinvest}
              onChange={(e) => setReinvest(e.target.checked)}
            />
            배당 재투자
          </label>
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
            <span className="dca-result__lab">
              누적 수익률 · {FREQ_WORD[data.freq]} {data.buys}회 매수
            </span>
          </div>
          <div className="bt-stats">
            <div className="bt-stat">
              <span className="bt-stat__k">투자 원금</span>
              <span className="bt-stat__v">{wonC(data.principal)}원</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">평가금액</span>
              <span className="bt-stat__v">{wonC(data.eval_value)}원</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">수익</span>
              <span className={`bt-stat__v ${up ? "index-card__chg--up" : "index-card__chg--down"}`}>
                {data.profit >= 0 ? "+" : ""}
                {wonC(data.profit)}원
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
          {data.notes.length > 0 ? (
            <ul className="dca-notes">
              {data.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          ) : null}
          <p className="bt-card__disc">
            {data.start_date && data.end_date ? `${data.start_date} ~ ${data.end_date} · ` : ""}
            과거 성과는 미래를 보장하지 않습니다.
          </p>
        </div>
      ) : (
        <p className="bt-card__hint">기간을 선택하면 정기 매수 결과를 계산합니다.</p>
      )}
    </section>
  );
}
