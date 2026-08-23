"""판정 전환 알림 라우트 — 설정 확인 · 기준선 조회 · 테스트 발송.

## 테스트 발송이 왜 필요한가
이 저장소는 Slack 도메인(hooks.slack.com 포함)이 이그레스 프록시에서 전부 막힌 환경에서
개발되었다. 규격은 Slack 공식 SDK 소스로 교차 확인했지만(src/alert_channels.py 주석)
**실제 발송은 한 번도 해보지 못했다.** 사용자가 자기 네트워크에서 이 엔드포인트를 한 번
때려보는 것이 유일한 실검증 경로다.

핸들러는 모두 `def`(async 아님)로 둔다 — FastAPI 가 스레드풀로 넘겨주므로, SMTP·HTTP
발송이 이벤트 루프를 막지 않는다.
"""
import logging
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Response

import db
from config import (
    DECISION_ALERT_CONFIRM_CYCLES,
    DECISION_ALERT_COOLDOWN_MINUTES,
    DECISION_ALERT_ENABLED,
    DECISION_ALERT_SIDE_ONLY,
    DECISION_ALERT_VIEWS,
    TIMEZONE,
)

from ..schemas import (
    AlertConfigResponse,
    AlertHistoryResponse,
    AlertStateResponse,
    AlertTestResponse,
)
from ..services import alerts

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# 테스트 발송 동시 실행을 1건으로 제한한다.
#
# 이 핸들러는 `def`(동기)라 FastAPI 가 anyio 스레드풀로 넘기는데, 한 번 호출이 Slack
# 15초 + SMTP 30초를 **순차로** 블로킹하며 토큰 1개를 최대 45초 점유한다. 기본 풀이
# 40토큰이므로 40건 동시 호출이면 모든 동기 엔드포인트(/api/health · /api/watchlist ·
# /api/paper/* · /api/market/status · /api/stocks/search …)가 함께 멈춘다.
# 세마포어 1개로 그 소진이 구조적으로 불가능해진다.
_test_lock = threading.Semaphore(1)


@router.get("/alerts/config", response_model=AlertConfigResponse)
def get_alert_config():
    now = datetime.now(ZoneInfo(TIMEZONE))
    return {
        "enabled": DECISION_ALERT_ENABLED,
        "channels": alerts.channels(),
        "views": list(DECISION_ALERT_VIEWS),
        "side_only": DECISION_ALERT_SIDE_ONLY,
        "confirm_cycles": DECISION_ALERT_CONFIRM_CYCLES,
        "cooldown_minutes": DECISION_ALERT_COOLDOWN_MINUTES,
        "in_window": alerts.in_alert_window(now),
        "baselines": len(db.get_decision_alert_state()),
    }


@router.get("/alerts/state", response_model=AlertStateResponse)
def get_alert_state():
    """저장된 기준선 — "어떤 판정을 마지막으로 알렸는지". 오알림 진단용."""
    state = db.get_decision_alert_state()
    items = [
        {
            "code": code, "view_kind": kind, "view": row["view"],
            "source": row["source"],
            "notified_at": row["notified_at"], "updated_at": row["updated_at"],
        }
        for (code, kind), row in sorted(state.items())
    ]
    return {"items": items}


@router.get("/alerts/history", response_model=AlertHistoryResponse)
def get_alert_history(limit: int = 100):
    """실제로 알림으로 나간 전환 이력(최신순).

    기준선(`/alerts/state`)은 종목·종류당 한 행만 들고 있어 "언제 어떻게 바뀌었나"에
    답하지 못한다. 이력은 그 질문 전용이다. 알림을 놓쳤거나 지난 며칠을 되짚을 때 쓴다.
    """
    return {"items": db.get_decision_alert_history(limit)}


@router.post("/alerts/test", response_model=AlertTestResponse)
def send_test_alert(response: Response):
    """설정된 채널로 예시 전환 1건을 발송한다. 기준선은 건드리지 않는다.

    DECISION_ALERT_ENABLED 와 장 시간대 게이트를 **우회한다** — 설정을 켜기 전에
    채널이 살아 있는지 먼저 확인하는 것이 이 엔드포인트의 목적이기 때문이다.

    동시 실행은 1건으로 제한한다(_test_lock 주석 참고). 이미 진행 중이면 429.
    """
    configured = alerts.channels()
    if not configured:
        return {
            "channels": [], "results": {},
            "detail": (
                "설정된 채널이 없습니다. DISCORD_WEBHOOK_URL · SLACK_WEBHOOK_URL 또는 "
                "SENDER_EMAIL·GMAIL_APP_PASSWORD·NOTIFY_EMAIL 을 .env 에 설정하세요."
            ),
        }

    if not _test_lock.acquire(blocking=False):
        response.status_code = 429
        response.headers["Retry-After"] = "45"
        return {
            "channels": configured, "results": {},
            "detail": "테스트 발송이 이미 진행 중입니다. 잠시 후 다시 시도하세요.",
        }

    try:
        now = datetime.now(ZoneInfo(TIMEZONE))
        sample = alerts.Transition(
            code="000000", name="[테스트] 발송 확인", kind="long",
            before="관망", after="매수", close=71200.0, change_pct=1.83,
        )
        # ★ 실패 사유를 함께 받는다. 이 엔드포인트는 진단 도구이므로 bool 만 주고
        #   "로그를 보세요"로 끝내면 목적을 달성하지 못한다 — 실제로 사용자가 로그에
        #   닿지 못해(다른 터미널의 포그라운드 프로세스) 원인 규명에 여러 왕복을 썼다.
        #   사유는 비밀(웹훅 URL·앱 비밀번호)을 지운 뒤 담긴다(alert_channels.scrub).
        reasons: dict[str, str] = {}
        results = alerts.dispatch([sample], now, reasons=reasons)
    finally:
        _test_lock.release()

    ok = [name for name, success in results.items() if success]
    failed = [name for name, success in results.items() if not success]

    detail = f"성공: {', '.join(ok) or '없음'}"
    if failed:
        detail += f" / 실패: {', '.join(failed)}"
        # 사유를 못 얻은 채널만 로그를 안내한다(태그는 alerts.log_tag 주석 참고).
        unexplained = [name for name in failed if not reasons.get(name)]
        if unexplained:
            hints = " · ".join(f"[{alerts.log_tag(name)}]" for name in unexplained)
            detail += f" (서버 로그의 {hints} 경고 확인)"
    return {
        "channels": configured, "results": results,
        "reasons": reasons, "detail": detail,
    }
