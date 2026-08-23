import type { PullbackCheck, PullbackStatus } from "../types";

interface PullbackCardProps {
  status: PullbackStatus | null;
  reason: string | null;
  checks: PullbackCheck[] | null | undefined;
}

// 6상태 전부 동일한 외곽선 칩으로 표시한다 — 눌림 국면 3종만 보여주면 하락장에서
// 기능 자체가 화면에서 사라져 "왜 안 나오지?"가 된다.
// 색은 기존 팔레트 재사용: 매수/관망은 SignalChip 과 동일 색, 이탈(무효)은 톤다운 적색,
// 중립 3종(추세아님/추세지속/데이터부족)은 데이터부족 아웃라인 색.
const STATUS_COLOR: Record<PullbackStatus, string> = {
  "눌림목 반등(매수후보)": "#4d7c0f",
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
  데이터부족: "일봉이 65개 이상 쌓이면 분석이 시작됩니다",
};

// 앞 3개(정배열/MA20 기울기/추세강도)가 추세 필터 — 순서 고정 계약(백엔드 schemas.py)
const TREND_FILTER_COUNT = 3;

const STATE_TEXT: Record<"ok" | "fail" | "waiting", string> = {
  ok: "충족",
  fail: "미충족",
  waiting: "대기",
};

/**
 * 눌림목 분석 카드 — 종목 상세 장기 탭 전용.
 *
 * 5단계 판정이 "지금 어느 국면인가"라면 이건 "지금이 진입 타이밍인가"를 답한다.
 * 상태 하나만 던지지 않고 6개 조건의 통과 여부를 함께 보여줘, 사용자가 **왜** 지금
 * 그 상태인지 스스로 읽을 수 있게 한다.
 */
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
            // 추세 필터(1~3)가 미충족이면 4~6은 실제 ok 값과 무관하게 '대기'로 낮춰
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
