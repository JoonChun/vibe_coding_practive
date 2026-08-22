import { TokenBanner } from "../components/TokenBanner";
import { useAlerts } from "../hooks/useAlerts";
import type { AlertStateItem } from "../types";

/** 채널명 → 실패 원인이 찍히는 서버 로그 태그. server/services/alerts.py::log_tag 와 같다. */
const LOG_TAGS: Record<string, string> = { email: "notifier" };
const logTag = (name: string) => LOG_TAGS[name] ?? name;

const CHANNEL_LABELS: Record<string, string> = {
  discord: "Discord",
  slack: "Slack",
  email: "이메일",
};

const VIEW_LABELS: Record<string, string> = { short: "단기", long: "장기" };

function yesNo(value: boolean): string {
  return value ? "예" : "아니오";
}

function StateRow({ item }: { item: AlertStateItem }) {
  return (
    <li className="alert-state__row">
      <span className="alert-state__code">{item.code}</span>
      <span className="alert-state__kind">
        {VIEW_LABELS[item.view_kind] ?? item.view_kind}
      </span>
      <span className="alert-state__view">{item.view}</span>
      <span className="alert-state__meta">
        {item.source ?? "출처 미기록"} · {item.notified_at ?? "발송 이력 없음"}
      </span>
    </li>
  );
}

/**
 * 알림 진단 페이지 — /alerts
 *
 * **설정을 바꾸는 화면이 아니다.** 알림 설정은 `.env` 에 있고 서버 재시작으로 반영된다
 * (비밀인 웹훅 URL·앱 비밀번호를 화면에서 다루지 않기 위한 선택이다). 이 화면이 답하는
 * 질문은 셋이다:
 *   · 어떤 채널이 실제로 **인식됐나** — 값이 오염돼 거부되면 여기서 비어 보인다.
 *   · 지금 알림이 나갈 조건인가 — ENABLED·장 시간대 게이트.
 *   · 무엇을 마지막으로 알렸나 — 기준선(오알림 진단의 출발점).
 * 그리고 테스트 발송 버튼으로 채널이 살아 있는지 확인한다.
 *
 * 이 화면이 없던 동안 위 세 가지를 curl 과 `.env` 편집으로 확인해야 했고, 실제로 그
 * 과정에서 값 오염(접두사 중복)을 찾는 데 여러 왕복이 걸렸다.
 */
export default function AlertsPage() {
  const {
    config, state, loading, error, errorStatus, refresh,
    testing, testResult, testError, runTest,
  } = useAlerts();

  if (errorStatus === 401) {
    return (
      <div className="app">
        <TokenBanner onSaved={refresh} />
        <header className="dash-header">
          <h1 className="dash-header__title">알림</h1>
        </header>
      </div>
    );
  }

  const channels = config?.channels ?? [];

  return (
    <div className="app">
      <header className="dash-header">
        <span className="dash-header__title">알림</span>
        <button type="button" className="paper-reset" onClick={refresh} disabled={loading}>
          새로고침
        </button>
      </header>

      <main className="dash-main">
        {error ? (
          <p className="panel__error" role="alert">{error}</p>
        ) : null}

        {/* ── 채널 ── */}
        <section aria-label="알림 채널">
          <h2 className="movers__title">알림 채널</h2>
          {loading && !config ? (
            <p className="movers__empty">불러오는 중…</p>
          ) : channels.length > 0 ? (
            <ul className="alert-chips">
              {channels.map((name) => (
                <li key={name} className="alert-chip">
                  {CHANNEL_LABELS[name] ?? name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="movers__empty">
              인식된 채널이 없습니다. <code>.env</code> 의 <code>DISCORD_WEBHOOK_URL</code> ·{" "}
              <code>SLACK_WEBHOOK_URL</code> 또는 Gmail 설정을 확인하세요. 값이 형식 검사에서
              거부된 경우에도 여기가 비므로, 서버 로그의 <code>[discord]</code> ·{" "}
              <code>[slack]</code> 경고를 함께 보세요.
            </p>
          )}

          <button
            type="button"
            className="alert-test-btn"
            onClick={runTest}
            disabled={testing || channels.length === 0}
          >
            {testing ? "발송 중…" : "테스트 발송"}
          </button>
          <p className="alert-note">
            테스트 발송은 ENABLED 플래그와 장 시간대 게이트를 <strong>우회</strong>하고,
            기준선을 건드리지 않습니다.
          </p>

          {testError ? (
            <p className="panel__error" data-testid="alert-test-result" role="alert">
              {testError}
            </p>
          ) : testResult ? (
            <div className="alert-result" data-testid="alert-test-result">
              <ul className="alert-result__list">
                {Object.entries(testResult.results).map(([name, ok]) => (
                  <li key={name} className="alert-result__row">
                    <span>{CHANNEL_LABELS[name] ?? name}</span>
                    <span className={ok ? "alert-ok" : "alert-fail"}>
                      {ok ? "성공" : `실패 — 서버 로그의 [${logTag(name)}] 경고 확인`}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="alert-note">{testResult.detail}</p>
            </div>
          ) : null}
        </section>

        {/* ── 발송 조건 ── */}
        <section aria-label="발송 조건">
          <h2 className="movers__title">발송 조건</h2>
          {config ? (
            <dl className="alert-facts">
              <div>
                <dt>알림 켜짐</dt>
                <dd className={config.enabled ? "alert-ok" : "alert-fail"}>
                  {yesNo(config.enabled)}
                </dd>
              </div>
              <div>
                <dt>지금 발송 시간대</dt>
                <dd className={config.in_window ? "alert-ok" : ""}>
                  {yesNo(config.in_window)}
                </dd>
              </div>
              <div>
                <dt>감시 판정</dt>
                <dd>{config.views.map((v) => VIEW_LABELS[v] ?? v).join(" · ")}</dd>
              </div>
              <div>
                <dt>측 변경만</dt>
                <dd>{yesNo(config.side_only)}</dd>
              </div>
              <div>
                <dt>확정 사이클</dt>
                <dd>{config.confirm_cycles}회 연속</dd>
              </div>
              <div>
                <dt>재알림 간격</dt>
                <dd>{config.cooldown_minutes}분</dd>
              </div>
            </dl>
          ) : (
            <p className="movers__empty">—</p>
          )}
          <p className="alert-note">
            설정은 <code>.env</code> 에서 바꾸고 서버를 재시작해야 반영됩니다. 웹훅 URL과 앱
            비밀번호는 그 자체가 비밀이라 이 화면에 표시하지 않습니다.
          </p>
        </section>

        {/* ── 기준선 ── */}
        <section aria-label="기준선">
          <h2 className="movers__title">
            기준선 {config ? `(${config.baselines}건)` : ""}
          </h2>
          <p className="alert-note">
            &quot;마지막으로 알린 판정&quot;입니다. 다음 알림은 이 값과 달라질 때만 나갑니다 —
            직전 사이클과 비교하지 않으므로 재시작으로 알림이 터지지 않습니다.
          </p>
          {state && state.items.length > 0 ? (
            <ul className="alert-state">
              {state.items.map((item) => (
                <StateRow key={`${item.code}-${item.view_kind}`} item={item} />
              ))}
            </ul>
          ) : (
            <p className="movers__empty">
              아직 기준선이 없습니다. 첫 수집 사이클이 조용히 시딩합니다(그 사이클에는 알림이
              나가지 않습니다).
            </p>
          )}
        </section>
      </main>

      <footer className="app-footer">
        ⓘ 알림은 기계적 판정 전환을 알릴 뿐입니다 · 투자 권유 아님
      </footer>
    </div>
  );
}
