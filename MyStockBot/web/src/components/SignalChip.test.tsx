import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SignalChip } from "./SignalChip";

describe("SignalChip", () => {
  it("판정 라벨을 그대로 그린다", () => {
    render(<SignalChip label="강력매수" kind="단기" />);
    expect(screen.getByLabelText("단기 관점: 강력매수")).toHaveTextContent("강력매수");
  });

  it("null·알 수 없는 값은 '데이터부족'으로 안전하게 떨어진다", () => {
    render(<SignalChip label={null} kind="장기" />);
    expect(screen.getByLabelText("장기 관점: 데이터부족")).toBeInTheDocument();
  });

  it("워밍업이면 '축적 중'으로 바꾸고 이유를 툴팁에 남긴다", () => {
    // 봉이 모자랄 때 백엔드는 0점=관망을 내므로, 그대로 '관망'을 보여주면
    // 사용자가 데이터 부재를 시장 판단으로 읽는다.
    render(<SignalChip label="관망" kind="단기" warming />);
    const chip = screen.getByLabelText("단기 관점: 축적 중");
    expect(chip).toHaveTextContent("축적 중");
    expect(chip).toHaveAttribute("title", expect.stringContaining("35개 미만"));
  });

  it("워밍업이 아니면 툴팁을 붙이지 않는다", () => {
    render(<SignalChip label="매수" kind="단기" />);
    expect(screen.getByLabelText("단기 관점: 매수")).not.toHaveAttribute("title");
  });
});
