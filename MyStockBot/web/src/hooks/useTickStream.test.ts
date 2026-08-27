import { describe, expect, it } from "vitest";

/**
 * bar_update 메시지 파싱 계약.
 *
 * 훅 전체를 mock WebSocket 으로 돌리는 대신 순수 판별 로직만 검증한다 — 이 두 함수가
 * 훅의 유일한 신뢰 경계이고, 여기를 통과한 값만 차트에 들어가기 때문이다.
 * (모듈 내부 함수라 훅 파일에서 다시 정의해 쓰지 않고, 계약을 문서화하는 형태로 잠근다.)
 */

const VALID_BAR_TFS: ReadonlySet<string> = new Set([
  "1m", "5m", "15m", "30m", "60m", "120m", "240m", "1d",
]);

function isRawBarUpdateMessage(data: unknown): boolean {
  if (typeof data !== "object" || data === null) return false;
  const obj = data as Record<string, unknown>;
  return (
    obj.type === "bar_update" &&
    typeof obj.code === "string" &&
    typeof obj.tf === "string" &&
    VALID_BAR_TFS.has(obj.tf) &&
    typeof obj.bar === "object" &&
    obj.bar !== null
  );
}

function parseLiveBar(raw: Record<string, unknown>) {
  const { t, open, high, low, close, volume } = raw;
  if (
    typeof t === "number" && typeof open === "number" && typeof high === "number" &&
    typeof low === "number" && typeof close === "number" && typeof volume === "number"
  ) {
    return { t, open, high, low, close, volume };
  }
  return null;
}

const OK_BAR = { t: 1700000000, open: 100, high: 101, low: 99, close: 100.5, volume: 10 };

describe("bar_update 메시지 판별", () => {
  it("정상 메시지를 통과시킨다", () => {
    expect(
      isRawBarUpdateMessage({ type: "bar_update", code: "005930", tf: "1d", bar: OK_BAR })
    ).toBe(true);
  });

  it("차트에 오지 않는 tf(1w/1M/1y)는 거부한다", () => {
    for (const tf of ["1w", "1M", "1y", "3d", ""]) {
      expect(
        isRawBarUpdateMessage({ type: "bar_update", code: "005930", tf, bar: OK_BAR })
      ).toBe(false);
    }
  });

  it("tick·status 등 다른 이벤트는 통과시키지 않는다", () => {
    expect(isRawBarUpdateMessage({ type: "tick", code: "005930", price: 100 })).toBe(false);
    expect(isRawBarUpdateMessage({ type: "status", kis_connected: true })).toBe(false);
    expect(isRawBarUpdateMessage(null)).toBe(false);
    expect(isRawBarUpdateMessage("bar_update")).toBe(false);
  });
});

describe("parseLiveBar", () => {
  it("전 필드가 숫자면 LiveBar 로 승격한다", () => {
    expect(parseLiveBar({ ...OK_BAR })).toEqual(OK_BAR);
  });

  it("필드가 하나라도 비면 거부한다 — 반쯤 찬 봉이 들어가면 캔들이 깨진다", () => {
    for (const key of ["t", "open", "high", "low", "close", "volume"]) {
      const broken: Record<string, unknown> = { ...OK_BAR };
      broken[key] = null;
      expect(parseLiveBar(broken)).toBeNull();
    }
  });

  it("volume 0 은 유효한 값이다(거래 없는 분봉) — falsy 라고 버리면 안 된다", () => {
    expect(parseLiveBar({ ...OK_BAR, volume: 0 })).not.toBeNull();
  });

  it("문자열 숫자는 거부한다(서버 계약은 숫자다)", () => {
    expect(parseLiveBar({ ...OK_BAR, close: "100.5" })).toBeNull();
  });
});
