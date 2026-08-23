import { useEffect, useState } from "react";
import { ApiError, getPaperEquity } from "../api";
import type { PaperEquityResponse } from "../types";
import { wonCompact as wonC } from "../utils/dcaShare";

/** 총자산(면적) vs 시드(점선 기준선) 미니 차트. DcaCurve 와 같은 시각 문법. */
function Curve({ points }: { points: PaperEquityResponse["points"] }) {
  if (points.length < 2) return null;
  const W = 300;
  const H = 90;
  const totals = points.map((p) => p.total);
  const max = Math.max(...totals);
  const min = Math.min(...totals);
  // 위아래로 5% 여백 — 변동이 작아도 곡선이 납작하게 눌리지 않게 한다.
  const pad = Math.max((max - min) * 0.05, 1);
  const hi = max + pad;
  const lo = min - pad;
  const x = (i: number) => (i / (points.length - 1)) * W;
  const y = (v: number) => H - ((v - lo) / (hi - lo)) * H;

  const line = points.map((p, i) => `${x(i).toFixed(1)},${y(p.total).toFixed(1)}`).join(" ");
  const area = `0,${H} ${line} ${W},${H}`;
  const first = points[0].total;
  const up = points[points.length - 1].total >= first;

  return (
    <svg
      className={`equity-curve${up ? "" : " equity-curve--down"}`}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label="모의투자 총자산 추이"
    >
      <polygon points={area} className="equity-curve__fill" />
      {/* 시작 시점 기준선 — 이 선 위/아래가 곧 누적 손익의 부호다 */}
      <line
        x1="0"
        x2={W}
        y1={y(first).toFixed(1)}
        y2={y(first).toFixed(1)}
        className="equity-curve__base"
      />
      <polyline points={line} className="equity-curve__line" fill="none" />
    </svg>
  );
}

/**
 * 모의투자 자산 추이 — 거래 이력을 되짚어 일자별 [현금 + 보유 평가]를 그린다.
 *
 * 백테스트가 "과거에 이 판정대로 샀다면"이라는 가정이라면, 이건 **실제 내 기록**이다.
 * 계좌 요약의 숫자 하나로는 안 보이는 "언제부터 벌었나/잃었나"를 보여준다.
 */
export function EquityCurve() {
  const [data, setData] = useState<PaperEquityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getPaperEquity()
      .then((res) => {
        if (cancelled) return;
        setData(res);
        setLoading(false);
      })
      .catch((e) => {
        if (cancelled) return;
        // 401 은 페이지 상위의 TokenBanner 가 이미 처리한다 — 여기선 조용히 숨긴다.
        setError(e instanceof ApiError && e.status === 401 ? null : "자산 추이를 불러오지 못했습니다.");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <section className="equity-card" aria-label="자산 추이">
        <p className="bt-card__hint">불러오는 중…</p>
      </section>
    );
  }
  if (error) {
    return (
      <section className="equity-card" aria-label="자산 추이">
        <p className="panel__error" role="alert">
          {error}
        </p>
      </section>
    );
  }
  if (!data || data.points.length === 0) {
    return null; // 거래가 없으면 카드 자체를 띄우지 않는다(빈 차트는 소음)
  }

  const first = data.points[0];
  const last = data.points[data.points.length - 1];
  const change = last.total - first.total;
  const changePct = first.total ? (change / first.total) * 100 : 0;
  const up = change >= 0;

  return (
    <section className="equity-card" aria-label="자산 추이">
      <div className="bt-card__header">
        <h3 className="bt-card__title">자산 추이</h3>
        <span className="bt-card__meta">
          {first.date} ~ {last.date}
        </span>
      </div>

      <div className="dca-result">
        <span className={`dca-result__pct ${up ? "index-card__chg--up" : "index-card__chg--down"}`}>
          {up ? "+" : ""}
          {changePct.toFixed(2)}%
        </span>
        <span className="dca-result__lab">
          시작 대비 {up ? "+" : ""}
          {wonC(change)}원
        </span>
      </div>

      <Curve points={data.points} />

      <div className="bt-stats">
        <div className="bt-stat">
          <span className="bt-stat__k">현금</span>
          <span className="bt-stat__v">{wonC(last.cash)}원</span>
        </div>
        <div className="bt-stat">
          <span className="bt-stat__k">주식 평가</span>
          <span className="bt-stat__v">{wonC(last.holdings_value)}원</span>
        </div>
        <div className="bt-stat">
          <span className="bt-stat__k">총자산</span>
          <span className="bt-stat__v">{wonC(last.total)}원</span>
        </div>
      </div>

      {data.notes.length > 0 ? (
        <ul className="bt-notes">
          {data.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
