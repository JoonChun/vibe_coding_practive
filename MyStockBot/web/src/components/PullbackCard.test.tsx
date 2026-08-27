import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PullbackCheck } from "../types";
import { PullbackCard } from "./PullbackCard";

const LABELS = [
  "정배열 (MA5>MA20>MA60)",
  "MA20 기울기 상승",
  "추세 강도 (ADX≥20)",
  "MA20 근접 (눌림 깊이)",
  "거래량 수축 (≤60%)",
  "반등 트리거 (양봉·전일고가·거래량)",
];

function checks(oks: boolean[]): PullbackCheck[] {
  return LABELS.map((label, i) => ({ label, ok: oks[i] }));
}

describe("PullbackCard", () => {
  it("status 가 없으면 아무것도 그리지 않는다(구버전 응답 방어)", () => {
    const { container } = render(
      <PullbackCard status={null} reason={null} checks={null} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("6상태 전부 칩으로 노출한다 — 하락장에서 기능이 사라지면 안 된다", () => {
    // 눌림 국면 3종만 보여주면 '왜 안 나오지?'가 된다(설계 의도).
    for (const status of ["추세아님", "추세지속", "데이터부족"] as const) {
      const { unmount } = render(
        <PullbackCard status={status} reason={null} checks={[]} />
      );
      expect(screen.getByLabelText(`눌림목 상태: ${status}`)).toBeInTheDocument();
      unmount();
    }
  });

  it("체크리스트를 순서 고정으로 그린다", () => {
    render(
      <PullbackCard
        status="눌림 진행중(관망)"
        reason="MA20 근접"
        checks={checks([true, true, true, true, true, false])}
      />
    );
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual(
      LABELS.map((l) => expect.stringContaining(l))
    );
  });

  it("추세 필터가 통과면 후행 조건은 실제 충족/미충족으로 표시한다", () => {
    render(
      <PullbackCard
        status="눌림 진행중(관망)"
        reason={null}
        checks={checks([true, true, true, true, true, false])}
      />
    );
    expect(screen.getByLabelText("거래량 수축 (≤60%): 충족")).toBeInTheDocument();
    expect(
      screen.getByLabelText("반등 트리거 (양봉·전일고가·거래량): 미충족")
    ).toBeInTheDocument();
  });

  it("추세 필터가 미충족이면 후행 3개는 '대기'로 낮춘다", () => {
    // 순차 파이프라인(추세 확인 → 눌림 깊이 → 트리거)임을 위계로 표현한다 —
    // 추세가 아닌데 '반등 트리거 충족'이라고 띄우면 오해를 부른다.
    render(
      <PullbackCard
        status="추세아님"
        reason="정배열 미충족"
        checks={checks([false, true, true, true, true, true])}
      />
    );
    expect(screen.getByLabelText("정배열 (MA5>MA20>MA60): 미충족")).toBeInTheDocument();
    expect(screen.getByLabelText("MA20 근접 (눌림 깊이): 대기")).toBeInTheDocument();
    expect(screen.getByLabelText("거래량 수축 (≤60%): 대기")).toBeInTheDocument();
    expect(
      screen.getByLabelText("반등 트리거 (양봉·전일고가·거래량): 대기")
    ).toBeInTheDocument();
  });

  it("checks 가 비면 체크리스트 없이 상태와 안내만 그린다(데이터부족)", () => {
    render(<PullbackCard status="데이터부족" reason="유효 봉수 부족" checks={[]} />);
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(screen.getByText(/65개 이상 쌓이면/)).toBeInTheDocument();
    expect(screen.getByText("유효 봉수 부족")).toBeInTheDocument();
  });
});
