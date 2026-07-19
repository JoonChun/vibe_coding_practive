import type { PullbackCheck, PullbackStatus } from "../types";

interface PullbackCardProps {
  status: PullbackStatus | null;
  reason: string | null;
  checks: PullbackCheck[] | null | undefined;
}

// 6종 상태 전부를 동일한 외곽선 칩으로 표시(과거엔 3종만 칩, 나머지는 회색 캡션이었으나
// "전 종목 하락장에서 기능 자체가 안 보인다"는 피드백을 넘어 항상 동일한 시각적 위계로 노출한다).
// 색은 기존 팔레트 재사용: 매수/관망은 SignalChip.CHIP_STYLES와 동일 색, 이탈(무효)은
// FactorBreakdown의 톤다운 적색을 재사용해 확정 판정보다 채도를 낮추고, 중립 3종(추세아님/추세지속/
// 데이터부족)은 SignalChip의 "데이터부족" 아웃라인 색(#9ca3af)을 재사용한다.
const STATUS_COLOR: Record<PullbackStatus, string> = {
  "눌림목 반등(매수후보)": "#65a30d",
  "눌림 진행중(관망)": "#6b7280",
  "눌림 이탈(무효)": "#f87171",
  추세아님: "#9ca3af",
  추세지속: "#9ca3af",
  데이터부족: "#9ca3af",
};

const STATUS_CAPTION: Record<PullbackStatus, string> = {
  추세아님: "상승 추세가 형성되면 눌림목 관찰이 시작됩니다",
  추세지속: "상승 추세 유지 중 — MA20 근처로 눌리면 관찰 구간입니다",
  "눌림 진행중(관망)": "눌림 구간 — 반등 트리거를 기다리는 중입니다",
  "눌림목 반등(매수후보)": "눌림목 반등 조건 충족 — 매수 후보입니다",
  "눌림 이탈(무효)": "MA20을 크게 이탈해 눌림목 시나리오가 무효화됐습니다",
  데이터부족: "일봉 데이터가 65개 이상 쌓이면 분석이 시작됩니다",
};

// 체크리스트 앞 3개(정배열/MA20 기울기/추세강도)는 추세 필터 — 순서 고정 계약(백엔드 schemas.py 참조)
const TREND_FILTER_COUNT = 3;

const STATE_TEXT: Record<"ok" | "fail" | "waiting", string> = {
  ok: "충족",
  fail: "미충족",
  waiting: "대기",
};

/** 눌림목 분석 — StockDetailPage 장기 탭 전용 독립 카드. 기여요인 분해 카드와 동일한
 * 시각 문법(카드 컨테이너·헤딩 좌 한글/우 영문 보조라벨)을 재사용하고, 상태칩 아래에
 * 6종 조건 체크리스트를 순차 파이프라인 위계로 보여준다. */
export function PullbackCard({ status, reason, checks }: PullbackCardProps) {
  if (status === null) return null;

  const color = STATUS_COLOR[status];
  const caption = STATUS_CAPTION[status];
  const hasChecks = Boolean(checks && checks.length > 0);
  const trendFilterPassed = hasChecks
    ? checks!.slice(0, TREND_FILTER_COUNT).every((c) => c.ok)
    : false;

  return (
    <div className="pullback-card">
      <div className="pullback-card__header">
        <h3 className="pullback-card__title">눌림목 분석</h3>
        <span className="pullback-card__meta">Pullback</span>
      </div>

      <span
        className="pullback-card__chip"
        style={{ color, borderColor: color }}
        aria-label={`눌림목 상태: ${status}`}
      >
        {status}
      </span>

      {hasChecks ? (
        <ul className="pullback-check-list">
          {checks!.map((check, i) => {
            // 추세 필터(1~3)가 미충족이면 4~6은 실제 ok 값과 무관하게 "대기" 시각으로 낮춰
            // 순차 파이프라인(추세 확인 → 눌림 깊이 → 트리거)임을 위계로 표현한다.
            const waiting = i >= TREND_FILTER_COUNT && !trendFilterPassed;
            const state: "ok" | "fail" | "waiting" = waiting ? "waiting" : check.ok ? "ok" : "fail";
            const glyph = state === "waiting" ? "○" : state === "ok" ? "✓" : "✗";
            return (
              <li
                key={check.label}
                className={`pullback-check pullback-check--${state}`}
                aria-label={`${check.label}: ${STATE_TEXT[state]}`}
              >
                <span className="pullback-check__glyph" aria-hidden="true">
                  {glyph}
                </span>
                <span className="pullback-check__label">{check.label}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      <div className="pullback-card__footer">
        <p className="pullback-card__caption">{caption}</p>
        {reason ? <p className="pullback-card__reason">{reason}</p> : null}
      </div>
    </div>
  );
}
