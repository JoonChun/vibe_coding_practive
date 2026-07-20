import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError,
  addWatchlistItem,
  deleteWatchlistItem,
  getWatchlist,
} from "../api";
import { AddStockForm } from "../components/AddStockForm";
import { DistributionStrip } from "../components/DistributionStrip";
import { RealtimeBadge } from "../components/RealtimeBadge";
import { StockCard, type StockCardData } from "../components/StockCard";
import { TokenBanner } from "../components/TokenBanner";
import { useRelativeTime } from "../hooks/useRelativeTime";
import { useSnapshot } from "../hooks/useSnapshot";
import { useTickStream } from "../hooks/useTickStream";
import type { DecisionView, SnapshotItem, WatchlistItem } from "../types";

type SortKey = "decision" | "change" | "name";

const DECISION_RANK: Record<DecisionView, number> = {
  강력매수: 0,
  매수: 1,
  관망: 2,
  매도: 3,
  강력매도: 4,
};

const EMPTY_DECISION_COUNTS: Record<DecisionView, number> = {
  강력매수: 0,
  매수: 0,
  관망: 0,
  매도: 0,
  강력매도: 0,
};

export default function DashboardPage() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [watchlistErrorStatus, setWatchlistErrorStatus] = useState<number | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("decision");
  // 삭제 실행취소용 — 방금 삭제한 종목(토스트). 타이머로 자동 소멸.
  const [undoItem, setUndoItem] = useState<{ code: string; name: string } | null>(null);
  const undoTimer = useRef<number | null>(null);

  const snapshot = useSnapshot();
  const relativeUpdatedAt = useRelativeTime(snapshot.lastUpdatedAt);
  const tickStream = useTickStream();

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await getWatchlist();
      setWatchlist(res.items);
      setWatchlistError(null);
      setWatchlistErrorStatus(null);
    } catch (err) {
      setWatchlistError(
        err instanceof ApiError ? err.message : "관심종목을 불러오지 못했습니다."
      );
      setWatchlistErrorStatus(err instanceof ApiError ? err.status : null);
    }
  }, []);

  useEffect(() => {
    void fetchWatchlist();
  }, [fetchWatchlist]);

  // 초기 watchlist 로드가 일시 장애로 실패해도, 스냅샷 폴링이 성공하면 재시도해 복구
  useEffect(() => {
    if (watchlistError !== null && snapshot.data !== null) {
      void fetchWatchlist();
    }
  }, [snapshot.data, watchlistError, fetchWatchlist]);

  const rows: StockCardData[] = useMemo(() => {
    const snapMap = new Map<string, SnapshotItem>();
    for (const item of snapshot.data?.items ?? []) {
      snapMap.set(item.code, item);
    }
    return watchlist
      .filter((item) => item.is_active)
      .map((item) => {
        const snap = snapMap.get(item.code);
        return {
          code: item.code,
          name: item.name,
          close: snap?.close ?? null,
          changePct: snap?.change_pct ?? null,
          shortView: snap?.short_view ?? null,
          longView: snap?.long_view ?? null,
          source: snap?.source ?? null,
          market: item.market ?? null,
        };
      });
  }, [watchlist, snapshot.data]);

  const existingCodes = useMemo(
    () => new Set(watchlist.map((item) => item.code)),
    [watchlist]
  );

  const distributionCounts = useMemo(() => {
    const counts: Record<DecisionView, number> = { ...EMPTY_DECISION_COUNTS };
    let total = 0;
    for (const row of rows) {
      if (row.shortView && row.shortView in counts) {
        counts[row.shortView as DecisionView] += 1;
        total += 1;
      }
    }
    return { counts, total };
  }, [rows]);

  const visibleRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered =
      q.length === 0
        ? rows
        : rows.filter(
            (row) =>
              row.name.toLowerCase().includes(q) || row.code.includes(q)
          );

    const sorted = [...filtered];
    if (sortKey === "decision") {
      sorted.sort(
        (a, b) =>
          (DECISION_RANK[a.shortView as DecisionView] ?? 5) -
          (DECISION_RANK[b.shortView as DecisionView] ?? 5)
      );
    } else if (sortKey === "change") {
      sorted.sort((a, b) => (b.changePct ?? -Infinity) - (a.changePct ?? -Infinity));
    } else {
      sorted.sort((a, b) => a.name.localeCompare(b.name, "ko"));
    }
    return sorted;
  }, [rows, query, sortKey]);

  // 언마운트 시 실행취소 타이머 정리(메모리 누수·잘못된 setState 방지)
  useEffect(() => {
    return () => {
      if (undoTimer.current !== null) window.clearTimeout(undoTimer.current);
    };
  }, []);

  function clearUndoTimer() {
    if (undoTimer.current !== null) {
      window.clearTimeout(undoTimer.current);
      undoTimer.current = null;
    }
  }

  // 낙관적 삭제: 즉시 목록에서 제거하고 '실행 취소' 토스트를 띄운다.
  async function handleDelete(code: string) {
    setDeleteError(null);
    const removed = watchlist.find((it) => it.code === code);
    // 낙관적 반영 — 화면에서 즉시 사라짐
    setWatchlist((prev) => prev.filter((it) => it.code !== code));
    if (removed) {
      clearUndoTimer();
      setUndoItem({ code: removed.code, name: removed.name });
      undoTimer.current = window.setTimeout(() => setUndoItem(null), 6000);
    }
    try {
      await deleteWatchlistItem(code);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 404)) {
        // 실패 시 롤백: 삭제를 되돌리고 오류 표시
        setDeleteError(
          err instanceof ApiError ? err.message : "종목 삭제에 실패했습니다."
        );
        clearUndoTimer();
        setUndoItem(null);
        await fetchWatchlist();
      }
    }
  }

  // 실행 취소: 방금 삭제한 종목을 다시 등록.
  async function handleUndo() {
    if (!undoItem) return;
    const { code, name } = undoItem;
    clearUndoTimer();
    setUndoItem(null);
    try {
      await addWatchlistItem({ code, name });
    } catch (err) {
      // 409(이미 존재)는 무시 — 어느 쪽이든 재조회로 정합성 확보
      if (!(err instanceof ApiError && err.status === 409)) {
        setDeleteError(
          err instanceof ApiError ? err.message : "실행 취소에 실패했습니다."
        );
      }
    } finally {
      await fetchWatchlist();
    }
  }

  const unauthorized = watchlistErrorStatus === 401 || snapshot.errorStatus === 401;
  const connectionFailed = Boolean(snapshot.error) && Boolean(watchlistError);
  const hasAnyData = watchlist.length > 0 || snapshot.data !== null;
  // 401(토큰 필요)일 때는 "서버에 연결할 수 없습니다" 배너로 오해하지 않도록 억제
  const showConnectionBanner =
    !unauthorized && (connectionFailed || (Boolean(snapshot.error) && !hasAnyData));

  return (
    <div className="app">
      {unauthorized ? (
        <TokenBanner
          onSaved={() => {
            void fetchWatchlist();
            snapshot.refresh();
          }}
        />
      ) : showConnectionBanner ? (
        <div className="banner banner--error" role="alert">
          <span>서버에 연결할 수 없습니다</span>
          <button
            type="button"
            className="banner__retry"
            onClick={() => {
              void fetchWatchlist();
              snapshot.refresh();
            }}
          >
            다시 시도
          </button>
        </div>
      ) : null}

      <header className="dash-header">
        <span className="dash-header__title">MyStockBot</span>
        <RealtimeBadge live={tickStream.connected && tickStream.kisConnected} />
      </header>

      <main className="dash-main">
        <AddStockForm
          query={query}
          onQueryChange={setQuery}
          existingCodes={existingCodes}
          onAdded={() => void fetchWatchlist()}
        />
        {watchlistError ? (
          <p className="panel__error" role="alert">
            {watchlistError}
          </p>
        ) : null}

        <DistributionStrip
          counts={distributionCounts.counts}
          total={distributionCounts.total}
        />

        <div className="watchlist-toolbar">
          <div>
            <h2 className="watchlist-toolbar__title">Watchlist</h2>
            <p className="watchlist-toolbar__updated">
              {snapshot.loading && !snapshot.data
                ? "불러오는 중…"
                : snapshot.lastUpdatedAt
                  ? `마지막 갱신: ${relativeUpdatedAt}`
                  : null}
              {snapshot.stale ? (
                <span className="watchlist-toolbar__stale">
                  {" "}
                  · 최신 갱신 실패, 이전 데이터 표시 중
                </span>
              ) : null}
            </p>
          </div>
          <label className="sort-select">
            <span className="sort-select__label">정렬</span>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              aria-label="관심종목 정렬 기준"
            >
              <option value="decision">판정순</option>
              <option value="change">등락률순</option>
              <option value="name">이름순</option>
            </select>
          </label>
        </div>

        {query.trim() && rows.length > 0 ? (
          <button
            type="button"
            className="filter-chip"
            onClick={() => setQuery("")}
            aria-label={`'${query.trim()}' 필터 지우기`}
          >
            필터: “{query.trim()}” <span aria-hidden="true">✕</span>
          </button>
        ) : null}

        {deleteError ? (
          <p className="panel__error" role="alert">
            {deleteError}
          </p>
        ) : null}

        {snapshot.loading && rows.length === 0 && !watchlistError ? (
          <ul className="stock-card-grid" aria-hidden="true">
            {[0, 1, 2, 3].map((i) => (
              <li key={i} className="stock-card stock-card--skeleton" />
            ))}
          </ul>
        ) : visibleRows.length === 0 ? (
          <p className="watchlist-empty">
            {rows.length === 0
              ? "등록된 관심종목이 없습니다. 위에서 종목을 검색해 추가해주세요."
              : `‘${query.trim()}’ 필터에 맞는 관심종목이 없습니다. 새 종목이면 위에서 추가하세요.`}
          </p>
        ) : (
          <ul className="stock-card-grid">
            {visibleRows.map((row) => (
              <StockCard
                key={row.code}
                row={row}
                onDelete={handleDelete}
                tick={tickStream.ticks[row.code] ?? null}
              />
            ))}
          </ul>
        )}
      </main>

      {undoItem ? (
        <div className="undo-toast" role="status">
          <span className="undo-toast__msg">{undoItem.name} 삭제됨</span>
          <button type="button" className="undo-toast__btn" onClick={() => void handleUndo()}>
            실행 취소
          </button>
        </div>
      ) : null}

      <footer className="app-footer">
        ⓘ 기계적 참고 지표 · 투자 권유 아님 · 최종 판단은 본인에게 있습니다
      </footer>
    </div>
  );
}
