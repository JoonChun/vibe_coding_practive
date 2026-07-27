import type { IndexItem } from "../types";

interface MarketBreadthBarProps {
  items: IndexItem[];
}

interface Totals {
  up: number;
  flat: number;
  down: number;
  limitUp: number;
  limitDown: number;
  total: number;
  /** 시장 폭을 제공한 지수 이름들 — 합산 범위를 화면에 정직하게 밝히기 위해 */
  sources: string[];
}

/**
 * 시장 폭을 제공한 지수만 합산한다(PRD §10.1: "코스피+코스닥 합산").
 *
 * 한쪽 지수만 KIS 현재지수 경로로 조회됐다면 그 한쪽만 합산되므로, 어디까지 합쳤는지를
 * 화면에 밝힌다 — "전체 시장"이라고 말해 놓고 절반만 세는 것을 막는다.
 */
function sumBreadth(items: IndexItem[]): Totals | null {
  const withBreadth = items.filter((it) => it.breadth !== null);
  if (withBreadth.length === 0) return null;

  const totals = withBreadth.reduce<Totals>(
    (acc, it) => {
      const b = it.breadth!;
      return {
        up: acc.up + b.up,
        flat: acc.flat + b.flat,
        down: acc.down + b.down,
        limitUp: acc.limitUp + b.limit_up,
        limitDown: acc.limitDown + b.limit_down,
        total: 0,
        sources: [...acc.sources, it.name],
      };
    },
    { up: 0, flat: 0, down: 0, limitUp: 0, limitDown: 0, total: 0, sources: [] }
  );

  const total = totals.up + totals.flat + totals.down;
  if (total === 0) return null;
  return { ...totals, total };
}

function pct(part: number, total: number): number {
  return (part / total) * 100;
}

/**
 * 시장 폭 — 상승·보합·하락 종목 수 비율 바 + 상한/하한 개수 (PRD §10.1 블록4).
 *
 * 국내 관례대로 상승=빨강, 하락=파랑. 데이터가 없으면(폴백 경로) 아무것도 그리지 않는다 —
 * 0으로 채운 빈 바를 보여주면 "오늘 아무 종목도 안 움직였다"로 오해된다.
 */
export function MarketBreadthBar({ items }: MarketBreadthBarProps) {
  const totals = sumBreadth(items);
  if (!totals) return null;

  const upPct = pct(totals.up, totals.total);
  const flatPct = pct(totals.flat, totals.total);
  const downPct = pct(totals.down, totals.total);
  const scope = totals.sources.join("+");

  return (
    <section className="breadth" aria-label="시장 폭">
      <div className="breadth__head">
        <h2 className="breadth__title">시장 폭</h2>
        <span className="breadth__scope">{scope} · {totals.total.toLocaleString("ko-KR")}종목</span>
      </div>

      <div
        className="breadth__bar"
        role="img"
        aria-label={`상승 ${totals.up}종목, 보합 ${totals.flat}종목, 하락 ${totals.down}종목`}
      >
        {totals.up > 0 ? (
          <span className="breadth__seg breadth__seg--up" style={{ width: `${upPct}%` }} />
        ) : null}
        {totals.flat > 0 ? (
          <span className="breadth__seg breadth__seg--flat" style={{ width: `${flatPct}%` }} />
        ) : null}
        {totals.down > 0 ? (
          <span className="breadth__seg breadth__seg--down" style={{ width: `${downPct}%` }} />
        ) : null}
      </div>

      <ul className="breadth__legend">
        <li>
          <i className="breadth__dot breadth__dot--up" aria-hidden="true" />
          상승 <b>{totals.up.toLocaleString("ko-KR")}</b>
          <span className="breadth__pct">{upPct.toFixed(0)}%</span>
        </li>
        <li>
          <i className="breadth__dot breadth__dot--flat" aria-hidden="true" />
          보합 <b>{totals.flat.toLocaleString("ko-KR")}</b>
        </li>
        <li>
          <i className="breadth__dot breadth__dot--down" aria-hidden="true" />
          하락 <b>{totals.down.toLocaleString("ko-KR")}</b>
          <span className="breadth__pct">{downPct.toFixed(0)}%</span>
        </li>
      </ul>

      {totals.limitUp > 0 || totals.limitDown > 0 ? (
        <p className="breadth__limits">
          상한 <b className="index-card__chg--up">{totals.limitUp}</b> · 하한{" "}
          <b className="index-card__chg--down">{totals.limitDown}</b>
        </p>
      ) : null}
    </section>
  );
}
