/** 원화(KRW) 표시용 포맷터 — 소수점 없이 반올림 후 천단위 콤마만 적용. */
export function formatKrw(value: number): string {
  return Math.round(value).toLocaleString("ko-KR");
}

/** epoch(초, UTC) → KST 기준 'YYYY-MM-DD'. 캔들 타임스탬프에서 "날짜"만 뽑아야 하는 곳
 * (차트 봉 탭 → 타임머신 프리필 등)에서 재사용. en-CA 로케일은 ISO 순서(연-월-일)로 포맷된다. */
export function epochToKstDateStr(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString("en-CA", {
    timeZone: "Asia/Seoul",
  });
}

/** 한국어 목적격 조사(을/를) 선택 — 마지막 글자에 받침이 있으면 "을", 없으면 "를".
 * 한글 음절이 아닌 문자로 끝나면(영문 종목명 등) 받침 없는 것으로 간주해 "를"을 기본값으로 쓴다. */
export function objectParticle(word: string): "을" | "를" {
  const trimmed = word.trim();
  const last = trimmed.charCodeAt(trimmed.length - 1);
  if (last >= 0xac00 && last <= 0xd7a3) {
    return (last - 0xac00) % 28 === 0 ? "를" : "을";
  }
  return "를";
}
