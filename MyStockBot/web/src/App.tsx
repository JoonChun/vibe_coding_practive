import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, deleteWatchlistItem, getWatchlist } from "./api";
import { AddStockForm } from "./components/AddStockForm";
import { TokenBanner } from "./components/TokenBanner";
import { WatchlistTable, type WatchlistRow } from "./components/WatchlistTable";
import { useSnapshot } from "./hooks/useSnapshot";
import type { SnapshotItem, WatchlistItem } from "./types";

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("ko-KR", {
      dateStyle: "medium",
      timeStyle: "medium",
    });
  } catch {
    return iso;
  }
}

export default function App() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [watchlistErrorStatus, setWatchlistErrorStatus] = useState<number | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const snapshot = useSnapshot();

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

  const rows: WatchlistRow[] = useMemo(() => {
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
          shortView: snap?.short_view ?? null,
          longView: snap?.long_view ?? null,
          source: snap?.source ?? null,
        };
      });
  }, [watchlist, snapshot.data]);

  async function handleDelete(code: string) {
    setDeleteError(null);
    try {
      await deleteWatchlistItem(code);
    } catch (err) {
      // 404(이미 삭제됨)는 무시하고 목록만 재조회
      if (!(err instanceof ApiError && err.status === 404)) {
        setDeleteError(
          err instanceof ApiError ? err.message : "종목 삭제에 실패했습니다."
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
          서버에 연결할 수 없습니다
        </div>
      ) : null}

      <header className="app-header">
        <h1>MyStockBot</h1>
        <div className="app-header__meta">
          {snapshot.loading && !snapshot.data ? (
            <span className="app-header__status">불러오는 중…</span>
          ) : snapshot.data ? (
            <>
              <span className="app-header__status">
                마지막 갱신: {formatDateTime(snapshot.data.generated_at)}
              </span>
              <span className="app-header__status">
                {snapshot.data.cache_hit ? "캐시 데이터" : "새로 수집됨"}
              </span>
              {snapshot.stale ? (
                <span className="app-header__status app-header__status--stale">
                  최신 갱신 실패 · 이전 데이터 표시 중
                </span>
              ) : null}
            </>
          ) : null}
        </div>
      </header>

      <main>
        <section className="panel">
          <h2>관심종목 추가</h2>
          <AddStockForm onAdded={() => void fetchWatchlist()} />
          {watchlistError ? (
            <p className="panel__error" role="alert">
              {watchlistError}
            </p>
          ) : null}
        </section>

        <section className="panel">
          <h2>관심종목 신호등</h2>
          {deleteError ? (
            <p className="panel__error" role="alert">
              {deleteError}
            </p>
          ) : null}
          <WatchlistTable rows={rows} onDelete={handleDelete} />
        </section>
      </main>

      <footer className="app-footer">
        ⓘ 기계적 참고 지표 · 투자 권유 아님 · 최종 판단은 본인에게 있습니다
      </footer>
    </div>
  );
}
