/** 원화(KRW) 표시용 포맷터 — 소수점 없이 반올림 후 천단위 콤마만 적용. */
export function formatKrw(value: number): string {
  return Math.round(value).toLocaleString("ko-KR");
}
