import { useState } from "react";
import { ApiError, getWhatIf } from "../api";
import type { WhatIfResponse } from "../types";
import { wonCompact as wonC } from "../utils/dcaShare";

interface TimeMachineCardProps {
  code: string;
}

const AMOUNTS = [
  { label: "100만원", value: 1_000_000 },
  { label: "500만원", value: 5_000_000 },
  { label: "1천만원", value: 10_000_000 },
];

/** 오늘로부터 n년 전 날짜(YYYY-MM-DD, KST 기준 로컬 계산). */
function yearsAgo(n: number): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - n);
  return d.toISOString().slice(0, 10);
}

const PRESETS = [
  { label: "1년 전", years: 1 },
  { label: "3년 전", years: 3 },
  { label: "5년 전", years: 5 },
];

/** 오늘(YYYY-MM-DD) — date input 의 max. 미래 날짜는 서버가 422 로 막지만 UI 에서 먼저 막는다. */
function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/**
 * "그날의 나" 타임머신 카드 — 종목 상세 하단.
 *
 * 답하는 질문: **"그때 샀으면 지금 얼마?"** 판정 로직을 쓰지 않고 단순 가격 비율만
 * 계산한다(배당·분할·수수료·세금 미반영). 코스피를 같은 기간으로 병치해 "시장보다
 * 나았나"를 함께 보여주고, 매수일 시점까지의 데이터만으로 재현한 '그날의 봇 판정'을
 * 참고로 붙인다 — 미래 데이터가 새어들지 않는다는 것은 서버 테스트로 봉인돼 있다.
 */
export function TimeMachineCard({ code }: TimeMachineCardProps) {
  const [date, setDate] = useState<string>(yearsAgo(3));
  const [amount, setAmount] = useState<number>(1_000_000);
  const [data, setData] = useState<WhatIfResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(next?: { date?: string; amount?: number }) {
    const d = next?.date ?? date;
    const a = next?.amount ?? amount;
    setLoading(true);
    setError(null);
    try {
      const res = await getWhatIf(code, d, a);
      setData(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "조회에 실패했습니다.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  // 서버가 200 으로 내려주는 '데이터 없음'(상장 전 등)은 예외가 아니라 정상 응답이다.
  const notice = data?.error ?? null;
  const ok = data !== null && notice === null;
  const up = (data?.return_pct ?? 0) >= 0;
  const beatsMarket =
    ok && data.kospi !== null && data.return_pct !== null
      ? data.return_pct - data.kospi.return_pct
      : null;

  return (
    <section className="bt-card" aria-label="그날의 나 — 타임머신">
      <div className="bt-card__header">
        <h3 className="bt-card__title">그날의 나</h3>
        <span className="bt-card__meta">그때 샀으면 지금 얼마?</span>
      </div>

      <div className="tm-controls">
        <div className="tm-row">
          <label className="tm-field">
            <span className="tm-field__label">매수일</span>
            <input
              type="date"
              className="tm-input"
              value={date}
              max={today()}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
          <div className="tm-presets">
            {PRESETS.map((p) => (
              <button
                key={p.years}
                type="button"
                className="tm-preset"
                disabled={loading}
                onClick={() => {
                  const d = yearsAgo(p.years);
                  setDate(d);
                  void run({ date: d });
                }}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="tm-row">
          <div className="tm-amounts">
            {AMOUNTS.map((a) => (
              <button
                key={a.value}
                type="button"
                className={"tm-amount" + (amount === a.value ? " tm-amount--on" : "")}
                disabled={loading}
                onClick={() => {
                  setAmount(a.value);
                  if (data) void run({ amount: a.value });
                }}
              >
                {a.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="tm-run"
            disabled={loading || !date}
            onClick={() => void run()}
          >
            {data ? "다시 계산" : "계산하기"}
          </button>
        </div>
      </div>

      {loading ? (
        <p className="bt-card__hint">계산 중…</p>
      ) : error ? (
        <p className="panel__error" role="alert">
          {error}
        </p>
      ) : notice ? (
        <p className="bt-card__hint">{notice}</p>
      ) : ok ? (
        <div className="bt-card__body">
          <div className="dca-result">
            <span
              className={`dca-result__pct ${up ? "index-card__chg--up" : "index-card__chg--down"}`}
            >
              {up ? "+" : ""}
              {data.return_pct?.toFixed(2)}%
            </span>
            <span className="dca-result__lab">
              {data.buy_date} 매수 · {data.multiple?.toFixed(1)}배
            </span>
          </div>

          <div className="bt-stats">
            <div className="bt-stat">
              <span className="bt-stat__k">투자 원금</span>
              <span className="bt-stat__v">{wonC(data.amount)}원</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">현재 평가</span>
              <span className="bt-stat__v">{wonC(data.eval_amount ?? 0)}원</span>
            </div>
            <div className="bt-stat">
              <span className="bt-stat__k">손익</span>
              <span className={`bt-stat__v ${up ? "index-card__chg--up" : "index-card__chg--down"}`}>
                {up ? "+" : ""}
                {wonC(data.profit ?? 0)}원
              </span>
            </div>
          </div>

          {/* 시장 대비 — 같은 금액을 코스피에 넣었다면 */}
          {data.kospi ? (
            <div className="tm-market">
              <div className="tm-market__row">
                <span className="tm-market__label">이 종목</span>
                <span className={up ? "index-card__chg--up" : "index-card__chg--down"}>
                  {up ? "+" : ""}
                  {data.return_pct?.toFixed(2)}%
                </span>
              </div>
              <div className="tm-market__row">
                <span className="tm-market__label">코스피</span>
                <span
                  className={
                    data.kospi.return_pct >= 0
                      ? "index-card__chg--up"
                      : "index-card__chg--down"
                  }
                >
                  {data.kospi.return_pct >= 0 ? "+" : ""}
                  {data.kospi.return_pct.toFixed(2)}%
                </span>
              </div>
              {beatsMarket !== null ? (
                <p className="tm-market__verdict">
                  시장 대비 {beatsMarket >= 0 ? "+" : ""}
                  {beatsMarket.toFixed(2)}%p — {beatsMarket >= 0 ? "초과 성과" : "미달"}
                </p>
              ) : null}
            </div>
          ) : null}

          {/* 그날의 봇 판정 — 매수일까지의 데이터만으로 재현 */}
          {data.bot_judgment ? (
            <div className="tm-bot">
              <div className="tm-bot__head">
                <span className="tm-bot__title">그날 봇은 뭐라 했을까</span>
                <span className="tm-bot__view">{data.bot_judgment.long_view ?? "데이터부족"}</span>
              </div>
              <p className="tm-bot__detail">
                MACD {data.bot_judgment.macd_1d ?? "—"} · RSI {data.bot_judgment.rsi_1d ?? "—"}
                {data.bot_judgment.pullback_status
                  ? ` · 눌림목 ${data.bot_judgment.pullback_status}`
                  : ""}
              </p>
              <p className="tm-bot__note">{data.bot_judgment.note}</p>
            </div>
          ) : null}

          <ul className="bt-notes">
            <li>단순 가격 기준 — 배당·액면분할·수수료·세금 미반영</li>
            <li>{data.buy_date} 종가 매수 → {data.current_date} 종가 평가</li>
            <li>과거 성과는 미래를 보장하지 않습니다</li>
          </ul>
        </div>
      ) : (
        <p className="bt-card__hint">
          매수일과 금액을 고르고 계산하면, 그때 샀을 경우의 손익과 그날의 봇 판정을 보여줍니다.
        </p>
      )}
    </section>
  );
}
