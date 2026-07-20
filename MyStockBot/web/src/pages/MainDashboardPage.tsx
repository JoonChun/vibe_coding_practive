import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { DistributionStrip } from "../components/DistributionStrip";
import { RealtimeBadge } from "../components/RealtimeBadge";
import { SignalChip } from "../components/SignalChip";
import { TokenBanner } from "../components/TokenBanner";
import { useIndices } from "../hooks/useIndices";
import { useSnapshot } from "../hooks/useSnapshot";
import { useTickStream } from "../hooks/useTickStream";
import type { DecisionView, IndexItem, SnapshotItem } from "../types";

const EMPTY_DECISION_COUNTS: Record<DecisionView, number> = {
  강력매수: 0,
  매수: 0,
  관망: 0,
  매도: 0,
  강력매도: 0,
};

function changeClass(pct: number | null): string {
  if (pct === null) return "index-card__chg--flat";
  if (pct > 0) return "index-card__chg--up";
  if (pct < 0) return "index-card__chg--down";
  return "index-card__chg--flat";
}

function formatIndexValue(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("ko-KR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function IndexCard({ item }: { item: IndexItem }) {
  const up = item.change_pct !== null && item.change_pct > 0;
  const down = item.change_pct !== null && item.change_pct < 0;
  const chgText =
    item.change_pct === null
      ? "—"
      : `${up ? "▲" : down ? "▼" : ""} ${item.change !== null ? Math.abs(item.change).toLocaleString("ko-KR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—"} (${item.change_pct > 0 ? "+" : ""}${item.change_pct.toFixed(2)}%)`;

  return (
    <div className="index-card">
      <span className="index-card__name">{item.name}</span>
      <span className="index-card__value">{formatIndexValue(item.value)}</span>
      {item.error ? (
        <span className="index-card__chg index-card__chg--flat">데이터 없음</span>
      ) : (
        <span className={`index-card__chg ${changeClass(item.change_pct)}`}>
          {chgText}
        </span>
      )}
    </div>
  );
}

/**
 * 메인 페이지 — 시장 대시보드 (/)
 * 코스피/코스닥 지수 + 내 관심종목 판정 분포·Top Movers 요약.
 */
export default function MainDashboardPage() {
  const indices = useIndices();
  const snapshot = useSnapshot();
  const tickStream = useTickStream();
  const navigate = useNavigate();

  const unauthorized =
    indices.errorStatus === 401 || snapshot.errorStatus === 401;

  const items: SnapshotItem[] = useMemo(
    () => snapshot.data?.items ?? [],
    [snapshot.data]
  );

  const distribution = useMemo(() => {
    const counts: Record<DecisionView, number> = { ...EMPTY_DECISION_COUNTS };
    let total = 0;
    for (const item of items) {
      const v = item.short_view;
      if (v && v in counts) {
        counts[v as DecisionView] += 1;
        total += 1;
      }
    }
    return { counts, total };
  }, [items]);

  const topMovers = useMemo(() => {
    return items
      .filter((it) => it.change_pct !== null && it.error === null)
      .sort(
        (a, b) => Math.abs(b.change_pct ?? 0) - Math.abs(a.change_pct ?? 0)
      )
      .slice(0, 3);
  }, [items]);

  return (
    <div className="app">
      {unauthorized ? (
        <TokenBanner
          onSaved={() => {
            indices.refresh();
            snapshot.refresh();
          }}
        />
      ) : null}

      <header className="dash-header">
        <span className="dash-header__title">MyStockBot</span>
        <RealtimeBadge live={tickStream.connected && tickStream.kisConnected} />
      </header>

      <main className="dash-main">
        <section className="index-grid" aria-label="시장 지수">
          {indices.data && indices.data.items.length > 0 ? (
            indices.data.items.map((idx) => (
              <IndexCard key={idx.code} item={idx} />
            ))
          ) : indices.loading ? (
            <>
              <div className="index-card index-card--skeleton" aria-hidden="true" />
              <div className="index-card index-card--skeleton" aria-hidden="true" />
            </>
          ) : (
            <p className="index-grid__error">지수를 불러오지 못했습니다.</p>
          )}
        </section>

        <DistributionStrip
          counts={distribution.counts}
          total={distribution.total}
        />

        <section className="movers" aria-label="관심종목 Top Movers">
          <h2 className="movers__title">오늘의 관심종목 Top Movers</h2>
          {topMovers.length === 0 ? (
            <p className="movers__empty">
              등록된 관심종목의 등락 데이터가 아직 없습니다.
            </p>
          ) : (
            <ul className="movers__list">
              {topMovers.map((it) => {
                const up = (it.change_pct ?? 0) > 0;
                const down = (it.change_pct ?? 0) < 0;
                return (
                  <li key={it.code}>
                    <button
                      type="button"
                      className="mover"
                      onClick={() => navigate(`/stocks/${it.code}`)}
                    >
                      <span className="mover__name">
                        {it.name}
                        <span className="mover__code">{it.code}</span>
                      </span>
                      <SignalChip label={it.short_view} kind="단기" />
                      <span
                        className={
                          "mover__chg " +
                          (up
                            ? "index-card__chg--up"
                            : down
                              ? "index-card__chg--down"
                              : "index-card__chg--flat")
                        }
                      >
                        {it.change_pct === null
                          ? "—"
                          : `${up ? "▲" : down ? "▼" : ""} ${it.change_pct > 0 ? "+" : ""}${it.change_pct.toFixed(2)}%`}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </main>

      <footer className="app-footer">
        ⓘ 기계적 참고 지표 · 투자 권유 아님 · 최종 판단은 본인에게 있습니다
      </footer>
    </div>
  );
}
