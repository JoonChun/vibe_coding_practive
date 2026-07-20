interface RealtimeBadgeProps {
  /** 브라우저↔서버 WS 연결 && 서버↔KIS 연결이 모두 살아있을 때 true */
  live: boolean;
}

/** 대시보드·상세 헤더 공통 실시간 상태 배지 — 살아있으면 초록 펄스, 아니면 회색 "지연" */
export function RealtimeBadge({ live }: RealtimeBadgeProps) {
  return (
    <span
      className={`realtime-badge${live ? "" : " realtime-badge--offline"}`}
      role="status"
    >
      <span className="realtime-badge__dot" aria-hidden="true" />
      <span>{live ? "실시간" : "지연"}</span>
    </span>
  );
}
