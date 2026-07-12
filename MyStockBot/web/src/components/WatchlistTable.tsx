import { useState } from "react";
import type { SignalView, SnapshotSource } from "../types";
import { SignalChip } from "./SignalChip";
import { SourceBadge } from "./SourceBadge";

export interface WatchlistRow {
  code: string;
  name: string;
  close: number | null;
  shortView: SignalView | null;
  longView: SignalView | null;
  source: SnapshotSource | null;
}

interface WatchlistTableProps {
  rows: WatchlistRow[];
  onDelete: (code: string) => Promise<void>;
}

export function WatchlistTable({ rows, onDelete }: WatchlistTableProps) {
  const [pendingCode, setPendingCode] = useState<string | null>(null);

  async function handleDeleteClick(code: string, name: string) {
    const confirmed = window.confirm(
      `${name} (${code}) 종목을 관심종목에서 삭제할까요?`
    );
    if (!confirmed) return;

    setPendingCode(code);
    try {
      await onDelete(code);
    } finally {
      setPendingCode(null);
    }
  }

  if (rows.length === 0) {
    return (
      <p className="watchlist-empty">
        등록된 관심종목이 없습니다. 위에서 종목을 추가해주세요.
      </p>
    );
  }

  return (
    <div className="watchlist-table-wrapper">
      <table className="watchlist-table">
        <thead>
          <tr>
            <th scope="col">코드</th>
            <th scope="col">종목명</th>
            <th scope="col">종가</th>
            <th scope="col">단기</th>
            <th scope="col">장기</th>
            <th scope="col">데이터 출처</th>
            <th scope="col">
              <span className="sr-only">삭제</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.code}>
              <td data-label="코드">{row.code}</td>
              <td data-label="종목명">{row.name}</td>
              <td data-label="종가">
                {row.close !== null ? row.close.toLocaleString("ko-KR") : "—"}
              </td>
              <td data-label="단기">
                <SignalChip label={row.shortView} kind="단기" />
              </td>
              <td data-label="장기">
                <SignalChip label={row.longView} kind="장기" />
              </td>
              <td data-label="데이터 출처">
                <SourceBadge source={row.source} />
              </td>
              <td data-label="삭제">
                <button
                  type="button"
                  className="watchlist-table__delete"
                  aria-label={`${row.name} (${row.code}) 관심종목에서 삭제`}
                  onClick={() => void handleDeleteClick(row.code, row.name)}
                  disabled={pendingCode === row.code}
                >
                  {pendingCode === row.code ? "삭제 중…" : "삭제"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
