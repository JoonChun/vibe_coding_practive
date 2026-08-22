"""판정 전환 알림 — 수집 사이클마다 판정이 바뀐 종목을 찾아 Slack·Gmail 로 알린다.

PRD §15.3 / §13-6. 기본 비활성(config.DECISION_ALERT_ENABLED).

## 설계에서 가장 중요한 것: **오알림을 만들지 않는 것**
판정 전환 알림의 실패 모드는 "알림이 안 온다"가 아니라 "쓸모없는 알림이 계속 온다"다.
한 번 신뢰를 잃으면 사용자가 알림을 꺼버리고, 그러면 기능 자체가 없는 것과 같다.
아래 게이트는 전부 **이 저장소 코드에서 실제로 확인한** 오알림 경로에 대응한다.

  ① 판정 없음(None·"데이터부족")은 알리지 않고 기준선도 건드리지 않는다.
     collector._error_item 은 판정을 None 으로 채우고, 60분봉이 없으면 "데이터부족"이
     나온다. 이걸 알리면 **수집 실패가 매매 신호로 보인다.** 게다가 지표에 필요한 봉이
     모자랄 때(MACD 35봉·RSI 15봉)는 "데이터부족"이 아니라 0점=관망이 나오므로,
     35번째 봉이 쌓이는 순간 가짜 '관망→매수' 전환이 생긴다.

  ② 기준선은 "직전 사이클"이 아니라 **"마지막으로 알린 판정"**이다(SQLite 영속).
     직전 사이클과 비교하면 (a) 서버 재시작마다 전 종목 알림이 터지고,
     (b) A↔B 왕복 시 매번 알림이 나간다. 마지막 알린 값과 비교하면 왕복해서 제자리로
     돌아온 판정은 같은 값이라 알리지 않는다 — 플랩 억제가 공짜로 따라온다.

  ③ 입력 구성이 바뀐 사이클은 알리지 않고 기준선만 조용히 옮긴다.
     재무데이터는 6시간 캐시라 부팅 직후 몇 사이클 뒤에 도착하고, 도착하면 장기 판정이
     재무 점수(±3)만큼 통째로 이동한다(예: 진입구간+중립 조합이 매수→강력매수).
     "첫 사이클을 기준선으로" 만으로는 막히지 않는다 — 2~3번째 사이클에 터진다.
     데이터 출처가 kis↔yfinance 로 바뀌는 경우도 같다: 시장이 아니라 입력이 바뀐 것이다.

  ④ 측(side)이 바뀔 때만 알린다(DECISION_ALERT_SIDE_ONLY, 기본 True).
     골든크로스(+2 강력매수)는 다음 봉에서 필연적으로 진입구간(+1 매수)으로 내려앉는다.
     즉 강력매수→매수는 골든크로스마다 **반드시** 생기는 구조적 사건이다
     (decision_rules.view_side 주석 참고). 같은 측 안의 등급 변화는 기준선만 갱신한다.

  ⑤ 히스테리시스 — 같은 판정이 연속 N사이클 유지돼야 확정.
     장중 마지막 봉은 미완성이라 계산이 흔들린다.

  ⑥ 쿨다운 — 같은 종목·같은 판정 종류에 최소 간격을 둔다.

  ⑦ 장 시간 외에는 아예 돌지 않는다.
     유휴 사이클 간격(600초)이 60분봉 신선도 기준(300초)보다 길어서 **주말·야간에도**
     매 사이클 외부 재조회가 일어난다. 야후가 실패했다가 복구되면 라벨이 재계산되므로,
     게이트가 없으면 일요일 새벽에 알림이 간다.

  ⑧ 발송이 성공했을 때만 기준선을 갱신한다.
     실패한 발송으로 기준선을 옮기면 그 전환은 영구히 유실된다.

## 스레드 안전
`process_cycle` 은 **수집 스레드에서, collector._state_lock 밖에서** 불린다.
그 락은 이벤트 루프 스레드가 직접 잡기 때문에(routers/snapshot.py 의 async 핸들러가
to_thread 없이 collector.get_state() 를 호출) 락 안에서 SMTP·HTTP 를 하면 서버 전체가
그만큼 멈춘다. 이 모듈은 그 락을 절대 만지지 않는다.

또한 이 경로는 **KIS 를 다시 부르지 않는다.** kis_auth.kis_throttle() 이 프로세스 전역
락을 잡고 0.5초 sleep 하므로, 알림이 KIS 를 부르면 수집 사이클이 그만큼 늘어난다.
스냅샷 아이템에 이미 들어 있는 값만 쓴다.

## 미완성 봉이라는 본질적 한계
장중 판정은 아직 닫히지 않은 봉으로 계산한 값이다. 10시에 나온 '관망→매수'가 15:30에
되돌아갈 수 있다. 이건 게이트로 없앨 수 있는 버그가 아니라 지표의 성질이므로,
알림 본문에 그렇게 적어 보낸다.
"""
import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import alert_channels
import db
import decision_rules
import market_calendar
import notifier
from config import (
    DECISION_ALERT_CONFIRM_CYCLES,
    DECISION_ALERT_COOLDOWN_MINUTES,
    DECISION_ALERT_ENABLED,
    DECISION_ALERT_MAX_ROWS,
    DECISION_ALERT_SIDE_ONLY,
    DECISION_ALERT_STATE_TTL_DAYS,
    DECISION_ALERT_VIEWS,
    TIMEZONE,
)

logger = logging.getLogger(__name__)

_KIND_LABELS = {"short": "단기", "long": "장기"}

# db.py 가 쓰는 UTC naive 타임스탬프 포맷과 동일.
_UTC_TS_FORMAT = "%Y-%m-%d %H:%M:%S"

_INTRADAY_CAVEAT = "장중 판정은 아직 닫히지 않은 봉으로 계산한 값이라 마감까지 바뀔 수 있습니다."

# 히스테리시스 카운터. 프로세스 메모리로 충분하다 — 재시작하면 확정에 N사이클이 다시
# 필요해질 뿐이고, 알림 기준선(무엇을 알렸는지)은 SQLite 에 있어 재시작에 안전하다.
_pending: dict[tuple[str, str], dict] = {}
_pending_lock = threading.Lock()


@dataclass(frozen=True)
class Transition:
    code: str
    name: str
    kind: str            # "short" | "long"
    before: str
    after: str
    close: float | None
    change_pct: float | None

    @property
    def key(self) -> tuple[str, str]:
        return (self.code, self.kind)

    @property
    def kind_label(self) -> str:
        return _KIND_LABELS.get(self.kind, self.kind)


# ────────────────────────────────────────────
# 순수 판정 — 외부 의존 없음(테스트가 dict 리터럴로 전부 검증 가능)
# ────────────────────────────────────────────

def in_alert_window(now: datetime) -> bool:
    """알림을 보낼 시간대인지 — 거래일의 정규장(09:00~15:30 KST) 안에서만 True.

    위 ⑦번 게이트. 마감 이후의 최종 판정은 크론 배치의 일일 리포트 메일이 담당한다.
    """
    if not market_calendar.is_trading_day(now.date()):
        return False
    return market_calendar.SESSION_OPEN <= now.time() <= market_calendar.SESSION_CLOSE


def _provenance(value) -> str | None:
    """알려진 데이터 출처만 남기고 나머지는 '알 수 없음'(None)으로 접는다.

    ★ 이게 없으면 게이트 ②(영속화)가 통째로 무효화된다:
    `collector._remembered_source()` 는 신선도 게이트로 fetch 를 건너뛸 때 실제 출처가 아닌
    센티널 문자열 `"store"` 를 돌려준다. 프로세스 재시작 직후 첫 사이클은 저장소가 신선하므로
    **항상** 저장소 서빙이고, 그러면 영속된 `"kis"` 와 달라져 게이트 ③이 전 종목 · 전
    view_kind 의 기준선을 현재 판정으로 무음 재시딩한다 — 장중 재기동 한 번에 그 구간의
    전환이 전부 사라진다.

    화이트리스트 방식이라 나중에 다른 센티널이 추가돼도 같은 사고가 재발하지 않는다.
    """
    return value if value in ("kis", "yfinance") else None


def _context(item: dict, kind: str) -> tuple[int, str | None]:
    """(재무 존재 비트마스크, 데이터 출처) — 위 ③번 게이트의 비교 대상.

    재무는 **필드별 존재 비트마스크**(per=1, pbr=2, roe=4 → 0~7)다. any() 로 접은 1비트로는
    "세 값 중 하나만 도착·소실한 사이클"을 구분할 수 없는데, 세 값은 각각 독립적으로 ±1 점을
    내고(decision_rules.RuleSet.fundamental_score) 관망 구간이 score==0 **단일 점**이라
    한 필드의 도착만으로도 측이 바뀐다. 적자·미공시 종목은 per 만 결측인 경우가 흔해서
    실제로 밟히는 경로다.

    단기 판정은 60분봉만 쓰므로 재무 마스크는 항상 0, 출처는 source_60m.
    """
    if kind == "long":
        mask = (
            int(item.get("per") is not None)
            | int(item.get("pbr") is not None) << 1
            | int(item.get("roe") is not None) << 2
        )
        return mask, _provenance(item.get("source"))
    return 0, _provenance(item.get("source_60m"))


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:19], _UTC_TS_FORMAT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _seed_row(code: str, kind: str, view: str, fund_mask: int, source) -> dict:
    """무음 시딩 행 — 기준선만 옮기고 알리지 않는다(notified_at 보존)."""
    return {
        "code": code, "view_kind": kind, "view": view,
        "fund_mask": fund_mask, "source": source, "notified": False,
    }


def diff(
    items: list[dict],
    state: dict[tuple[str, str], dict],
    pending: dict[tuple[str, str], dict],
    now: datetime,
    *,
    kinds: tuple[str, ...],
    side_only: bool,
    confirm_cycles: int,
    cooldown_minutes: int,
    state_ttl_days: int,
) -> tuple[list[Transition], list[dict], dict[tuple[str, str], dict]]:
    """스냅샷 아이템 목록 → (확정 전환, 무음 시딩 행, 새 히스테리시스 상태).

    부수효과가 없다. DB 쓰기·발송은 호출부(process_cycle)가 한다.
    튜닝 값은 기본값 없이 **전부 인자로 받는다** — 기본값으로 두면 import 시점에 고정되어
    설정을 바꿔도(테스트 포함) 반영되지 않는다.

    반환된 `pending` 에는 **발화한 키도 남아 있다** — 발송이 실패하면 다음 사이클에
    즉시 재시도하기 위함이다. 발송 성공 시 호출부가 그 키를 지운다.
    """
    transitions: list[Transition] = []
    seeds: list[dict] = []
    new_pending: dict[tuple[str, str], dict] = {}

    for item in items:
        code = item.get("code")
        if not code:
            continue
        name = item.get("name") or code

        for kind in kinds:
            view = item.get(f"{kind}_view")
            # ① 판정 없음 — 알리지 않고 기준선도 건드리지 않는다.
            side = decision_rules.view_side(view)
            if side is None:
                continue

            key = (code, kind)
            fund_mask, source = _context(item, kind)
            prev = state.get(key)

            # 기준선이 없거나 오래 방치됐으면 조용히 시딩(부팅 폭발·재추가 헛알림 방지).
            if prev is None or _is_stale(prev, now, state_ttl_days):
                seeds.append(_seed_row(code, kind, view, fund_mask, source))
                continue

            # ③ 입력 구성이 바뀐 사이클 — 판정 변화의 원인이 시장이 아니다.
            #
            # 출처는 **양쪽이 모두 알려진 값일 때만** 비교한다. 알 수 없음(None)과
            # 비교하면 재시작 직후 첫 사이클이 전 종목을 무음 재시딩한다(_provenance 주석).
            source_changed = (
                source is not None
                and prev["source"] is not None
                and prev["source"] != source
            )
            if prev["fund_mask"] != fund_mask or source_changed:
                seeds.append(_seed_row(code, kind, view, fund_mask, source))
                continue

            prev_view = prev["view"]
            if side_only and decision_rules.view_side(prev_view) == side:
                # ④ 같은 측 안의 등급 변화 — 알리지 않지만 기준선은 최신 라벨로 옮겨
                #    다음 알림 본문의 '이전 판정'이 실제 직전 값이 되게 한다.
                if view != prev_view:
                    seeds.append(_seed_row(code, kind, view, fund_mask, source))
                continue
            if not side_only and view == prev_view:
                continue

            # ⑤ 히스테리시스 — 같은 판정이 연속 유지된 사이클 수를 센다.
            previous = pending.get(key)
            count = (previous["count"] + 1) if previous and previous["view"] == view else 1
            if count < confirm_cycles:
                new_pending[key] = {"view": view, "count": count}
                continue

            # ⑥ 쿨다운 — 아직이면 카운터를 유지해 쿨다운이 풀리는 즉시 발화한다.
            if _in_cooldown(prev, now, cooldown_minutes):
                new_pending[key] = {"view": view, "count": count}
                continue

            new_pending[key] = {"view": view, "count": count}
            transitions.append(Transition(
                code=code, name=name, kind=kind,
                before=prev_view, after=view,
                close=item.get("close"), change_pct=item.get("change_pct"),
            ))

    return transitions, seeds, new_pending


def _is_stale(prev: dict, now: datetime, ttl_days: int) -> bool:
    if ttl_days <= 0:
        return False
    updated = _parse_ts(prev.get("updated_at"))
    if updated is None:
        return False
    return (now.astimezone(timezone.utc) - updated) > timedelta(days=ttl_days)


def _in_cooldown(prev: dict, now: datetime, cooldown_minutes: int) -> bool:
    if cooldown_minutes <= 0:
        return False
    notified = _parse_ts(prev.get("notified_at"))
    if notified is None:  # 아직 한 번도 알린 적 없음 → 쿨다운 없음
        return False
    return (now.astimezone(timezone.utc) - notified) < timedelta(minutes=cooldown_minutes)


# ────────────────────────────────────────────
# 렌더링
# ────────────────────────────────────────────

def _finite(value) -> float | None:
    """유한한 실수만 통과. NaN·inf 는 None — 포맷하면 "nan원"/"inf원" 이 그대로 찍힌다."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _price_text(t: Transition) -> str:
    """"71,200원 (+1.83%)" 또는 값이 없으면 빈 문자열."""
    close = _finite(t.close)
    if close is None:
        return ""
    pct = _finite(t.change_pct)
    return f"{close:,.0f}원" if pct is None else f"{close:,.0f}원 ({pct:+.2f}%)"


def _price_suffix(t: Transition) -> str:
    """줄 끝에 붙이는 형태(" · 71,200원 …"). 표 셀에는 _price_text 를 쓴다.

    예전에는 표 쪽에서 이 값을 `lstrip(' ·')` 로 되돌렸는데, lstrip 은 **문자 집합**을
    지우는 함수라 접두어 제거 용도로는 위험하다(집합에 든 문자가 값 앞에 오면 같이 깎인다).
    두 형태를 따로 만들어 되돌릴 필요를 없앴다.
    """
    text = _price_text(t)
    return f" · {text}" if text else ""


def render_text(
    transitions: list[Transition],
    now: datetime,
    total: int | None = None,
    dialect: alert_channels.Dialect = alert_channels.SLACK_DIALECT,
) -> str:
    """채널 본문. 마크업 문법은 `dialect` 가 결정한다.

    **굵게 문법이 채널마다 다르다** — Slack mrkdwn 은 `*굵게*`(별표 하나), Discord 는
    표준 마크다운의 `**굵게**`. 서로 바꿔 보내면 별표가 글자로 보인다. 그래서 렌더러가
    문법을 하드코딩하지 않고 방언에서 받아 쓴다.

    `transitions` 는 **이미 잘린(발송 대상) 목록**이고 `total` 은 이번 사이클의 전체
    전환 수다. 여기서 자르지 않는 이유: 예전에는 렌더러가 잘랐는데 호출부는 전체 목록으로
    기준선을 옮겨서, 어느 채널에도 실린 적 없는 전환이 '알린 판정'으로 기록되고 다시는
    보고되지 않았다(게이트 ⑧ 위반). 자르는 주체를 호출부 하나로 모았다.

    보간되는 값은 전부 방언의 이스케이프를 통과한다 — 종목명이 외부 입력이기 때문이다.
    의도한 굵게·기울임 마크업은 이스케이프 대상이 아니므로 줄 단위로 감싸지 않는다.

    마지막 방어선으로 `dialect.max_chars` 를 넘으면 잘라낸다. 넘긴 채로 보내면 Discord 는
    400 을 주고, 알림 엔진은 실패를 재시도하므로 **사이클마다 영구히 실패**한다.
    정상 경로에서는 호출부가 행 수를 미리 맞추므로(`fit_rows`) 여기까지 오지 않는다.
    """
    text = _render_raw(transitions, now, total, dialect)
    if dialect.max_chars is not None and len(text) > dialect.max_chars:
        logger.warning(
            "[alerts] %s 본문이 상한(%d자)을 넘어 잘라 보냅니다 — 전환 %d건",
            dialect.name, dialect.max_chars, len(transitions),
        )
        text = text[: dialect.max_chars - 1] + "…"
    return text


def _render_raw(
    transitions: list[Transition],
    now: datetime,
    total: int | None,
    dialect: alert_channels.Dialect,
) -> str:
    """길이 상한을 적용하지 **않은** 본문.

    `fit_rows` 가 이걸 쓴다. `render_text` 를 쓰면 그쪽이 이미 잘라서 돌려주므로
    `len(...) <= max_chars` 가 **항상 참**이 되어 넘침을 영원히 감지하지 못한다
    (실제로 그렇게 짰다가 테스트에서 잡혔다 — 안전장치가 계측을 무력화한 경우다).
    """
    esc = dialect.escape
    bold = dialect.bold
    total = len(transitions) if total is None else total

    lines = [f"{bold('MyStockBot 판정 전환')} {total}건 · {now.strftime('%m/%d %H:%M')}"]
    for t in transitions:
        lines.append(
            f"• {bold(esc(t.name))}({esc(t.code)}) {esc(t.kind_label)} "
            f"{esc(t.before)} → {bold(esc(t.after))}{esc(_price_suffix(t))}"
        )
    remaining = total - len(transitions)
    if remaining > 0:
        lines.append(f"… 나머지 {remaining}건은 다음 사이클에 이어서 알립니다")
    lines.append(dialect.italic(_INTRADAY_CAVEAT))
    return "\n".join(lines)


def fit_rows(
    transitions: list[Transition],
    now: datetime,
    total: int,
    dialect: alert_channels.Dialect,
    cap: int,
) -> int:
    """`dialect.max_chars` 안에 들어가는 최대 행 수(최소 1, 최대 `cap`).

    Discord 의 2000자 제한이 실제로 걸린다: 상한 30건 × 행당 60자면 넘는다. 넘기면 400
    이고, 실패한 발송은 다음 사이클에 재시도되므로 **고칠 때까지 계속 실패**한다.
    행 수를 미리 줄여 보내면 넘친 만큼은 다음 사이클로 자연 이월된다.
    """
    if dialect.max_chars is None or cap <= 0:
        return max(0, cap)
    fitted = 0
    for k in range(1, cap + 1):
        if len(_render_raw(transitions[:k], now, total, dialect)) <= dialect.max_chars:
            fitted = k
        else:
            break
    # 1건조차 넘치는 병리적 경우(비정상적으로 긴 종목명)에도 1건은 보낸다 —
    # render_text 가 마지막에 잘라내므로 400 은 나지 않는다.
    return max(1, fitted)


def render_email(
    transitions: list[Transition], now: datetime, total: int | None = None
) -> tuple[str, str]:
    """(제목, HTML 본문). 종목명은 외부 입력이라 이스케이프한다.

    `render_text` 와 동일하게 **자르지 않는다** — 호출부가 자른 목록을 받는다.
    """
    total = len(transitions) if total is None else total
    shown = transitions
    subject = f"[MyStockBot] 판정 전환 {total}건 - {now.strftime('%Y-%m-%d %H:%M')}"

    rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{notifier.esc(t.code)}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{notifier.esc(t.name)}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{notifier.esc(t.kind_label)}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;color:#6b7280;'>"
        f"{notifier.esc(t.before)}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;font-weight:bold;'>"
        f"{notifier.esc(t.after)}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;text-align:right;'>"
        f"{notifier.esc(_price_text(t) or '—')}</td>"
        f"</tr>"
        for t in shown
    )
    more = (
        f"<p style='color:#6b7280;font-size:13px;'>"
        f"… 나머지 {total - len(shown)}건은 다음 사이클에 이어서 알립니다</p>"
        if total > len(shown) else ""
    )
    html_body = f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;max-width:680px;margin:0 auto;padding:24px;color:#111827;">
  <h2 style="margin-bottom:4px;">판정 전환 {total}건</h2>
  <p style="color:#6b7280;margin-top:0;">{notifier.esc(now.strftime('%Y-%m-%d %H:%M:%S %Z'))}</p>
  <table style="border-collapse:collapse;width:100%;font-size:14px;">
    <thead>
      <tr style="background:#f9fafb;">
        <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">종목코드</th>
        <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">종목명</th>
        <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">구분</th>
        <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">이전</th>
        <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">현재</th>
        <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:right;">현재가</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  {more}
  <p style="margin-top:24px;font-size:12px;color:#9ca3af;">{notifier.esc(_INTRADAY_CAVEAT)}</p>
</body>
</html>"""
    return subject, html_body


# ────────────────────────────────────────────
# 발송 · 사이클 처리
# ────────────────────────────────────────────

def channels() -> list[str]:
    """설정된 알림 채널 이름 목록."""
    names = [c.name for c in alert_channels.enabled_channels()]
    if notifier.email_enabled():
        names.append("email")
    return names


# 채널명 → **로그에 실제로 찍히는 태그**.
#
# 웹훅 채널은 이름 그대로 찍힌다(`[discord]` · `[slack]`) — _post_json 에 넘기는 label 이
# 채널명과 같기 때문이고, tests/test_alert_channels.py 가 그 동일성을 잠근다.
# 이메일만 다르다: 발송하는 주체가 src/notifier.py 이고 그쪽 로그 태그는 `[notifier]` 다.
# 그래서 `[email]` 이라는 태그는 로그에 **존재하지 않는다**. 실패 안내에 채널명을 그대로
# 쓰면 사용자가 없는 태그를 grep 하며 원인을 못 찾는다(실측으로 걸렸다).
_LOG_TAGS = {"email": "notifier"}


def log_tag(channel_name: str) -> str:
    """그 채널의 실패 원인이 찍히는 로그 태그. 안내 문구용."""
    return _LOG_TAGS.get(channel_name, channel_name)


def dispatch(
    transitions: list[Transition], now: datetime, total: int | None = None
) -> dict[str, bool]:
    """설정된 모든 채널로 발송. {채널명: 성공여부}.

    `transitions` 는 **실제로 실어 보낼 목록**이고 `total` 은 이번 사이클 전체 건수다
    (잘린 경우 본문에 잔여 안내를 넣기 위함). 자르는 주체는 호출부 하나다.

    채널마다 마크업 방언이 달라 본문을 각각 렌더링하지만, **실어 보내는 전환 목록은 같다** —
    채널별로 다르게 자르면 어느 채널에 무엇이 갔는지가 갈라져 기준선 이동 판단이 모호해진다.
    """
    results: dict[str, bool] = {}
    for channel in alert_channels.enabled_channels():
        results[channel.name] = channel.send(
            render_text(transitions, now, total, channel.dialect)
        )
    if notifier.email_enabled():
        subject, html_body = render_email(transitions, now, total)
        results["email"] = notifier.send_html(subject, html_body)
    return results


def process_cycle(items: list[dict], now: datetime | None = None) -> dict:
    """수집 사이클 1회분 처리. collector 가 _state_lock **밖에서** 호출한다.

    반환은 진단용 요약이다(라우터·테스트가 읽는다). 예외를 던지지 않는다.
    """
    if not DECISION_ALERT_ENABLED:
        return {"enabled": False, "reason": "DECISION_ALERT_ENABLED 미설정", "sent": 0}

    now = now or datetime.now(ZoneInfo(TIMEZONE))

    configured = channels()
    if not configured:
        # 채널이 없으면 기준선도 건드리지 않는다. 나중에 채널을 붙이면 그때 첫 사이클이
        # 조용히 시딩하므로, 붙이는 순간 전 종목 알림이 터지는 일이 없다.
        return {"enabled": True, "reason": "알림 채널 미설정", "sent": 0, "channels": []}

    if not in_alert_window(now):
        return {"enabled": True, "reason": "장 시간 외", "sent": 0, "channels": configured}

    state = db.get_decision_alert_state()
    with _pending_lock:
        transitions, seeds, new_pending = diff(
            items, state, _pending, now,
            kinds=DECISION_ALERT_VIEWS,
            side_only=DECISION_ALERT_SIDE_ONLY,
            confirm_cycles=DECISION_ALERT_CONFIRM_CYCLES,
            cooldown_minutes=DECISION_ALERT_COOLDOWN_MINUTES,
            state_ttl_days=DECISION_ALERT_STATE_TTL_DAYS,
        )
        _pending.clear()
        _pending.update(new_pending)

    if seeds:
        db.upsert_decision_alert_state(seeds)

    if not transitions:
        return {
            "enabled": True, "reason": "전환 없음", "sent": 0,
            "channels": configured, "seeded": len(seeds),
        }

    # ⑧-a 한 메시지 상한. **여기 한 곳에서만 자른다.**
    #     예전에는 렌더러가 각자 잘랐는데 기준선은 전체 목록으로 옮겨서, 어느 채널에도
    #     실린 적 없는 전환이 '알린 판정'으로 기록되고 다시는 보고되지 않았다 —
    #     지수 급락일처럼 알림이 가장 필요한 날에만 터지고, 무엇이 유실됐는지 복원할
    #     경로도 없었다(로그도 건수만 남긴다).
    #     이제 잘린 꼬리는 _pending 에 count>=confirm 상태로 남고 notified_at 도
    #     건드려지지 않으므로 다음 사이클에 그대로 발화한다 = 자연 페이지네이션.
    total = len(transitions)
    cap = DECISION_ALERT_MAX_ROWS if DECISION_ALERT_MAX_ROWS > 0 else total
    cap = min(cap, total)
    # 채널마다 본문 길이 상한이 다르므로(Discord 2000자) **가장 빡빡한 쪽**에 맞춘다.
    # 채널별로 다르게 자르면 어느 채널에 무엇이 실렸는지가 갈라져, 기준선을 어디까지
    # 옮겨야 하는지 판단할 수 없게 된다. 자르는 지점은 끝까지 이 한 곳이다.
    for channel in alert_channels.enabled_channels():
        cap = min(cap, fit_rows(transitions, now, total, channel.dialect, cap))
    shown = transitions[:cap]

    results = dispatch(shown, now, total)
    delivered = [name for name, ok in results.items() if ok]

    if delivered:
        # ⑧-b 성공한 발송에 **실린 것만** 기준선을 옮긴다.
        by_code = {item.get("code"): item for item in items}
        notified_rows = []
        for t in shown:
            fund_mask, source = _context(by_code.get(t.code, {}), t.kind)
            notified_rows.append({
                "code": t.code, "view_kind": t.kind, "view": t.after,
                "fund_mask": fund_mask, "source": source, "notified": True,
            })
        db.upsert_decision_alert_state(notified_rows)

        # ⑧-c 이력. 기준선과 **같은 조건**으로 남긴다 — 발송 성공에 실린 것만.
        #
        # 기준선(decision_alert_state)은 종목·종류당 한 행만 들고 게이트 판단에 쓰이는
        # 캐시라 "언제 어떻게 바뀌었나"에 답할 수 없다. 이력은 그 질문 전용이다.
        # 실패한 채널은 싣지 않는다 — 어디로 갔는지가 사실과 달라진다.
        # 이력 쓰기가 실패해도 발송·기준선은 이미 끝났으므로 사이클을 멈추지 않는다.
        delivered_label = ",".join(sorted(delivered))
        try:
            db.insert_decision_alert_history([
                {
                    "code": t.code, "name": t.name, "view_kind": t.kind,
                    "before_view": t.before, "after_view": t.after,
                    "close": t.close, "change_pct": t.change_pct,
                    "channels": delivered_label,
                }
                for t in shown
            ])
        except Exception as e:
            logger.warning("[alerts] 이력 기록 실패(발송은 완료됨): %s", e)

        with _pending_lock:
            for t in shown:
                _pending.pop(t.key, None)
        if total > len(shown):
            logger.info(
                "[alerts] 판정 전환 %d건 중 %d건 발송(%s) — 나머지 %d건은 다음 사이클",
                total, len(shown), ", ".join(delivered), total - len(shown),
            )
        else:
            logger.info("[alerts] 판정 전환 %d건 발송(%s)", total, ", ".join(delivered))
    else:
        # 전 채널 실패 — 기준선을 옮기지 않아 다음 사이클에 재시도한다.
        logger.warning("[alerts] 판정 전환 %d건 발송 실패 — 다음 사이클 재시도", total)

    return {
        "enabled": True, "reason": "발송" if delivered else "발송 실패",
        "sent": len(shown) if delivered else 0,
        "transitions": total,
        "deferred": total - len(shown),
        "channels": configured, "results": results, "seeded": len(seeds),
    }
