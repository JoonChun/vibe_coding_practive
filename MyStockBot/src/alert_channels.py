"""알림 채널 — Slack Incoming Webhook.

## 왜 Slack 인가
prd.md 가 카카오톡 알림을 접은 이유는 "액세스 토큰 갱신 부담"이었다. Slack Incoming
Webhook 은 **토큰이 없다** — 인증 헤더를 쓰지 않고 URL 자체가 자격증명이라, 갱신 로직이
구조적으로 필요하지 않다. 카카오톡을 접게 만든 그 이유가 여기엔 존재하지 않는다.

## 규격 출처 (이 저장소 규칙: 추측 금지)
이 개발 환경에서는 slack.com · api.slack.com · docs.slack.dev · hooks.slack.com 이
전부 이그레스 프록시에서 403 CONNECT 로 막혀 있다. 따라서
  · 공식 문서 페이지를 열어 확인할 수 없었고,
  · **실제 발송으로 검증하지도 못했다.**
그래서 Slack 이 직접 배포하는 SDK 소스 코드에서 규격을 교차 확인했다(문서가 아니라 구현):

  · slackapi/python-slack-sdk
      - `slack_sdk/webhook/client.py`         : POST 본문 구성, 응답 처리
      - `slack_sdk/webhook/internal_utils.py` : `_build_request_headers()` —
            `Content-Type: application/json;charset=utf-8` + User-Agent 만 붙이고
            **Authorization 헤더를 넣지 않는다.**
      - 본문 허용 키: text / blocks / attachments / unfurl_links / unfurl_media / metadata
  · slackapi/java-slack-sdk
      - 성공 판정이 HTTP 200 + **본문 문자열 `ok`** (JSON 이 아니다).
      - 실패는 400/403/404 + `invalid_payload` / `channel_not_found` /
        `channel_is_archived`, 유량제한은 429 + `Retry-After`.

이 구현이 `requests` 도 `slack_sdk` 도 쓰지 않는 이유:
  1. 의존성 추가 없이 stdlib(`urllib.request`)로 충분하다 — 요청 1개, 헤더 2개다.
  2. `slack_sdk` 는 DEBUG 레벨에서 **웹훅 URL 전체를 로그에 찍는다.** 그 URL 이 비밀이다.

## 보안
웹훅 URL 그 자체가 자격증명이고, Slack 은 공개된 곳에서 발견된 URL 을 자동 폐기한다.
→ **URL 을 로그·예외 메시지·API 응답에 절대 싣지 않는다.** 아래 코드가 URL 을 문자열로
   내보내는 경로는 없다(에러 메시지에는 상태코드와 Slack 이 준 오류 코드만 담는다).
"""
import json
import logging
import os
import urllib.error
import urllib.request

from config import SLACK_WEBHOOK_URL_ENV_KEY

logger = logging.getLogger(__name__)

# 검증된 규격: 이 접두어의 URL 만 허용한다.
# 오타나 잘못 붙여넣은 값으로 임의 호스트에 POST 하지 않기 위한 방어선이다.
_SLACK_WEBHOOK_PREFIX = "https://hooks.slack.com/"

_TIMEOUT_SECONDS = 15
_SUCCESS_BODY = "ok"


def slack_webhook_url() -> str | None:
    """설정된 웹훅 URL. 미설정이거나 형식이 다르면 None."""
    url = os.environ.get(SLACK_WEBHOOK_URL_ENV_KEY, "").strip()
    if not url:
        return None
    if not url.startswith(_SLACK_WEBHOOK_PREFIX):
        # URL 을 로그에 남기지 않는다 — 잘못된 값이라도 비밀일 수 있다.
        logger.warning(
            "[slack] SLACK_WEBHOOK_URL 형식이 다릅니다(%s 로 시작해야 함) — 발송 비활성",
            _SLACK_WEBHOOK_PREFIX,
        )
        return None
    return url


def slack_enabled() -> bool:
    return slack_webhook_url() is not None


def send_slack(text: str, blocks: list[dict] | None = None) -> bool:
    """Incoming Webhook 으로 메시지 1건 발송. 성공하면 True.

    `text` 는 blocks 를 쓰더라도 항상 넣는다 — 알림 미리보기·접근성 폴백에 쓰인다.
    예외를 밖으로 던지지 않는다(알림 실패가 수집 사이클을 멈추게 하지 않도록).
    """
    url = slack_webhook_url()
    if url is None:
        return False

    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            # 검증된 헤더 구성(python-slack-sdk internal_utils._build_request_headers).
            # Authorization 헤더는 **없다** — 웹훅은 토큰을 쓰지 않는다.
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": "MyStockBot/1.0 (+github.com/JoonChun/vibe_coding_practive)",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
            if response.status == 200 and body == _SUCCESS_BODY:
                return True
            logger.warning("[slack] 발송 실패: HTTP %s / %s", response.status, body[:200])
            return False
    except urllib.error.HTTPError as e:
        # Slack 은 실패 이유를 본문 문자열로 준다(invalid_payload · channel_not_found 등).
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace").strip()[:200]
        except Exception:
            pass
        retry_after = e.headers.get("Retry-After") if e.headers else None
        suffix = f" (Retry-After={retry_after})" if retry_after else ""
        logger.warning("[slack] 발송 실패: HTTP %s / %s%s", e.code, body, suffix)
        return False
    except Exception as e:
        # ★ URL 을 담지 않는다. urllib 예외는 보통 URL 을 문자열에 포함하지 않지만,
        #   혹시 모를 노출을 막기 위해 예외 타입만 남긴다.
        logger.warning("[slack] 발송 실패: %s", type(e).__name__)
        return False
