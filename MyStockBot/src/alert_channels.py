"""알림 채널 — Slack / Discord Incoming Webhook.

## 왜 웹훅인가
prd.md 가 카카오톡 알림을 접은 이유는 "액세스 토큰 갱신 부담"이었다. 두 채널 모두
**토큰이 없다** — 인증 헤더를 쓰지 않고 URL 자체가 자격증명이라 갱신 로직이 구조적으로
필요하지 않다. 카카오톡을 접게 만든 그 이유가 여기엔 존재하지 않는다.

## 규격 출처 (이 저장소 규칙: 추측 금지)

### Slack
slack.com · api.slack.com · docs.slack.dev · hooks.slack.com 이 이 개발 환경의
이그레스 프록시에서 전부 403 CONNECT 로 막혀 있다. 공식 문서 페이지를 열 수 없었고
**실제 발송으로 검증하지도 못했다.** 그래서 Slack 이 직접 배포하는 SDK 소스에서 확인했다:
  · slackapi/python-slack-sdk `slack_sdk/webhook/internal_utils.py`
      `_build_request_headers()` — `Content-Type: application/json;charset=utf-8` +
      User-Agent 만 붙이고 **Authorization 헤더를 넣지 않는다.**
      본문 허용 키: text / blocks / attachments / unfurl_links / unfurl_media / metadata
  · slackapi/java-slack-sdk — 성공 판정이 HTTP 200 + **본문 문자열 `ok`**(JSON 아님).
      실패는 400/403/404 + invalid_payload / channel_not_found / channel_is_archived.

### Discord
discord.com · discord.dev 도 똑같이 차단되어 있다. 그래서 Discord **공식 문서 저장소**
(`discord/discord-api-docs`, `developers/resources/webhook.mdx` · `.../message.mdx`)를
클론해 원문으로 확인했다:
  · Execute Webhook: `POST /webhooks/{webhook.id}/{webhook.token}`
  · "Same as above, except this call does not require authentication."(L204)
      → **Authorization 헤더 없음** (토큰이 URL 경로에 있다)
  · 본문 필드는 `content` (**최대 2000자**). content/embeds/components/file/poll 중
      최소 하나는 필수.
  · "Returns a message or `204 No Content` depending on the `wait` query parameter."
      `wait` 기본값은 `false`.
  · ★ `wait=false` 일 때 **"a message that is not saved does not return an error"** —
      조용히 버려진 메시지를 성공으로 읽게 된다. 이 저장소의 알림 엔진은 "발송 성공 시에만
      기준선 이동" 규칙을 지키므로, 그걸 성공으로 읽으면 그 전환이 **영구 유실**된다.
      → 그래서 항상 `?wait=true` 를 붙이고 200 을 기대한다(204 도 관용적으로 허용).
  · 유량제한: HTTP 429 + `Retry-After` 헤더 및 JSON 본문의 `retry_after`(float, 초).
  · ★ 멘션 차단은 **구조적으로** 가능하다 — 공식 경고문:
      "If you are passing user-generated strings into message content, consider
       sanitizing the data ... and using `allowed_mentions` to prevent unexpected
       mentions."
      웹훅의 기본값은 `{"parse": ["users"]}` 라서 @everyone/@here 는 기본 미파싱이지만
      **유저 멘션은 파싱된다.** `{"parse": []}` 로 보내면 어떤 멘션도 파싱되지 않는다.
      텍스트 이스케이프와 달리 문자 조합으로 우회할 수 없다 — Slack 경로보다 강한 보장이다.

`requests` 도 `slack_sdk` 도 쓰지 않는 이유:
  1. 의존성 추가 없이 stdlib(`urllib.request`)로 충분하다 — 요청 1개, 헤더 2개다.
  2. `slack_sdk` 는 DEBUG 레벨에서 **웹훅 URL 전체를 로그에 찍는다.** 그 URL 이 비밀이다.

## 보안
웹훅 URL 그 자체가 자격증명이다(Slack 은 공개된 URL 을 자동 폐기하는데, 안전해지는 게
아니라 알림이 조용히 죽는다).
→ **URL 을 로그·예외 메시지·API 응답에 절대 싣지 않는다.** 아래 코드에 URL 을 문자열로
   내보내는 경로는 없고, 그 성질을 테스트로 잠갔다(tests/test_alert_channels.py).
"""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from config import DISCORD_WEBHOOK_URL_ENV_KEY, SLACK_WEBHOOK_URL_ENV_KEY

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15
_USER_AGENT = "MyStockBot/1.0 (+github.com/JoonChun/vibe_coding_practive)"

# 검증된 규격의 호스트만 허용한다 — 오타나 잘못 붙여넣은 값으로 임의 호스트에
# POST 하지 않기 위한 방어선이다.
_SLACK_WEBHOOK_PREFIXES = ("https://hooks.slack.com/",)
# discordapp.com 은 discord.com 이전의 구 도메인이고 여전히 동작한다(예전에 만든 웹훅 URL).
_DISCORD_WEBHOOK_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
)

_SLACK_SUCCESS_BODY = "ok"


# ────────────────────────────────────────────
# 이스케이프 — 채널마다 제어 문자가 다르다
# ────────────────────────────────────────────

def escape_mrkdwn(value) -> str:
    """Slack 본문에 **보간되는 값**을 안전하게 만든다.

    왜 필요한가 — 종목명은 Google Sheets·외부 API 에서 오는 미검증 문자열이고,
    `<` 는 Slack 의 제어 시퀀스 시작 문자다. 종목명에 `<!channel>` 이 들어가면 알림이
    나갈 때마다 채널 전원에게 푸시가 간다.

    확인한 것: `slackapi/python-slack-sdk` tests/web/classes/test_objects.py 에서
    `ChannelLink()` → `"<!channel|channel>"`, `HereLink()` → `"<!here|here>"` —
    즉 `<!...>` 가 실제 멘션 제어 시퀀스임이 Slack 자체 코드로 확인된다.
    그리고 `slackapi/java-slack-sdk` Field.java 는 마크업을 담는 `value` 를
    "must be escaped as normal"(L24), 마크업이 없는 `title` 만 "will be escaped for
    you"(L19) 라고 적어 **이스케이프가 호출자 책임**임을 밝힌다.

    확인하지 못한 것: `& < >` → `&amp; &lt; &gt;` 라는 정확한 엔티티 대응을 Slack 소유
    코드에서 문장으로 찾지는 못했다(문서 사이트 차단). 이 치환을 택한 이유는 위에서 확인된
    주입 경로를 확실히 무력화하기 때문이고, 매핑이 세부에서 다르더라도 실패 모드는
    `&amp;` 가 글자로 보이는 **표시상의 문제**이지 멘션 주입이 아니다.

    `&` 를 **먼저** 치환해야 한다 — 나중에 하면 `&lt;` 의 `&` 를 다시 이스케이프한다.
    """
    return (
        str("" if value is None else value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# Discord 마크다운에서 서식 의미를 갖는 문자들. 백슬래시 이스케이프가 관례다.
# `\` 를 **먼저** 처리해야 한다(나중에 하면 앞서 넣은 백슬래시를 다시 이스케이프한다).
_DISCORD_MD_CHARS = ("\\", "`", "*", "_", "~", "|", ">")


def escape_markdown(value) -> str:
    """Discord 본문에 보간되는 값의 **표시**를 보호한다.

    ★ 이건 보안 장치가 아니다. 멘션 차단은 `allowed_mentions: {"parse": []}` 가
    구조적으로 처리하고(위 모듈 주석 참고), 이 함수는 종목명에 `**`·`||`·`` ` `` 같은
    문자가 섞여 메시지 서식이 깨지는 것을 막는 **표시 위생**일 뿐이다.
    공식 문서도 "characters which cause unexpected message formatting" 을 경고한다.
    """
    text = str("" if value is None else value)
    for ch in _DISCORD_MD_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text


# ────────────────────────────────────────────
# 마크업 방언 — 렌더러가 채널별 문법을 하드코딩하지 않도록
# ────────────────────────────────────────────

@dataclass(frozen=True)
class Dialect:
    """채널의 마크업 문법 + 길이 제한.

    굵게 문법이 채널마다 다른 것이 함정이다 — Slack mrkdwn 은 `*굵게*`(별표 하나),
    Discord 는 표준 마크다운의 `**굵게**` 다. 서로 바꿔 보내면 별표가 글자로 보인다.
    """
    name: str
    bold_wrap: str
    italic_wrap: str
    escape: Callable[[object], str]
    # 본문 최대 길이. None 은 "이 저장소가 1차 출처로 확인하지 못했다"는 뜻이고
    # "무제한"이라는 주장이 아니다(추측 금지 — 확인 못 한 숫자를 적지 않는다).
    max_chars: int | None = None

    def bold(self, text) -> str:
        return self.bold_wrap.format(text)

    def italic(self, text) -> str:
        return self.italic_wrap.format(text)


SLACK_DIALECT = Dialect(
    name="slack",
    bold_wrap="*{}*",
    italic_wrap="_{}_",
    escape=escape_mrkdwn,
    max_chars=None,   # Slack 웹훅 text 상한을 1차 출처로 확인하지 못했다
)

DISCORD_DIALECT = Dialect(
    name="discord",
    bold_wrap="**{}**",
    italic_wrap="_{}_",
    escape=escape_markdown,
    # 공식 문서 webhook.mdx L237: content "up to 2000 characters".
    # 초과하면 400 이고, 알림 엔진은 실패한 발송을 재시도하므로 사이클마다 계속 실패한다.
    max_chars=2000,
)


# ────────────────────────────────────────────
# URL 취득 · 검증
# ────────────────────────────────────────────

def _common_problem(url: str, prefixes: tuple[str, ...]) -> str | None:
    """벤더와 무관하게 확실히 틀린 값. 문제 설명(URL 미포함) 또는 None.

    ★ `startswith` 만으로는 부족하다 — 실사용에서 이 값이 통과했다:
        DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/https://discordapp.com/...
      README 의 예시 줄(접두사) 뒤에 복사한 URL 을 이어 붙인 형태다. 앞 33자가 맞으니
      검사를 통과해 `/api/alerts/config` 는 "설정됨"이라 보고했고, 오류는 한참 뒤
      Discord 의 404 로만 드러났다. 시작 시점에 잡아야 하는 문제다.
    """
    if not url.startswith(prefixes):
        return f"{' | '.join(prefixes)} 중 하나로 시작해야 합니다"
    if any(ch.isspace() for ch in url):
        return "값 안에 공백·줄바꿈이 섞여 있습니다"
    if url.count("://") > 1:
        return (
            "URL 이 두 개 이어붙어 있습니다(`://` 가 2번 등장) — 앞쪽 템플릿 접두사를 "
            "지우고 복사한 URL 하나만 남기세요"
        )
    return None


def _discord_path_problem(url: str) -> str | None:
    """Discord 웹훅 경로 형태 검사. 문제 설명(URL 미포함) 또는 None.

    1차 출처: discord/discord-api-docs
      · webhook.mdx L207 — `POST /webhooks/{webhook.id}/{webhook.token}`
        (베이스가 `/api` 이므로 경로 조각은 api·webhooks·id·token 4개)
      · webhook.mdx L23 — webhook `id` 의 타입은 `snowflake`
      · reference.mdx L136 — snowflake 는 "up to 64 bits (e.g. a uint64)" 이고
        HTTP API 에서는 항상 문자열로 온다 → 숫자로만 이루어진다
    길이는 문서로 확인하지 못했으므로 고정하지 않는다.
    """
    segments = [s for s in urllib.parse.urlsplit(url).path.split("/") if s]
    if len(segments) != 4 or segments[0] != "api" or segments[1] != "webhooks":
        return (
            f"경로가 /api/webhooks/{{id}}/{{token}} 형태가 아닙니다"
            f"(조각 {len(segments)}개, 정상은 4개)"
        )
    webhook_id = segments[2]
    # isascii() 를 함께 본다 — isdigit() 만으로는 아라비아-인도 숫자 등도 참이 된다.
    if not (webhook_id.isascii() and webhook_id.isdigit()):
        return "webhook id 자리가 숫자가 아닙니다(공식 문서: id 는 snowflake)"
    return None


def _webhook_url(
    env_key: str,
    prefixes: tuple[str, ...],
    label: str,
    extra_check: Callable[[str], str | None] | None = None,
) -> str | None:
    url = os.environ.get(env_key, "").strip()
    if not url:
        return None
    problem = _common_problem(url, prefixes)
    if problem is None and extra_check is not None:
        problem = extra_check(url)
    if problem is not None:
        # URL 을 로그에 남기지 않는다 — 잘못된 값이라도 비밀일 수 있다.
        logger.warning("[%s] %s 값이 올바르지 않습니다 — %s. 발송 비활성",
                       label, env_key, problem)
        return None
    return url


def slack_webhook_url() -> str | None:
    # Slack 은 경로 형태를 1차 출처로 확인하지 못했다(hooks.slack.com 문서가 이 환경에서
    # 전부 차단). 확인한 것만 검사한다 — 없는 규격을 지어내면 정상 URL 을 막을 수 있다.
    return _webhook_url(SLACK_WEBHOOK_URL_ENV_KEY, _SLACK_WEBHOOK_PREFIXES, "slack")


def discord_webhook_url() -> str | None:
    return _webhook_url(
        DISCORD_WEBHOOK_URL_ENV_KEY, _DISCORD_WEBHOOK_PREFIXES, "discord",
        _discord_path_problem,
    )


def slack_enabled() -> bool:
    return slack_webhook_url() is not None


def discord_enabled() -> bool:
    return discord_webhook_url() is not None


# ────────────────────────────────────────────
# 발송
# ────────────────────────────────────────────

# HTTP 상태별 **조치** 안내.
#
# 왜 필요한가 — 원인만 찍어도(`HTTP 404 / {"message":"Unknown Webhook","code":10015}`)
# 사용자는 그다음에 무엇을 해야 하는지 모른다. 실측으로 그 상황이 그대로 나왔다.
#
# 문구는 추측이 아니라 1차 출처 기준이다. discord/discord-api-docs 저장소,
# docs/developers/topics/opcodes-and-status-codes.mdx:
#   · L125 `404 (NOT FOUND)` = "The resource at the location specified doesn't exist."
#   · L155 JSON code `10015` = "Unknown webhook"
#   · L121 `400 (BAD REQUEST)` = "The request was improperly formatted, or the server
#     couldn't understand it."
# Slack 쪽은 웹훅 오류 본문 목록을 1차 출처로 확인하지 못했으므로 **표를 만들지 않는다** —
# 그럴듯한 문구를 지어내면 잘못된 방향으로 디버깅을 보낸다.
_DISCORD_STATUS_HINTS = {
    404: (
        "웹훅이 존재하지 않습니다(공식 문서: 404 = 지정한 리소스 없음, code 10015 = "
        "Unknown webhook). Discord 채널 편집 → 연동 → 웹훅에서 새로 만들어 "
        "DISCORD_WEBHOOK_URL 을 교체하세요. .env 값에 인라인 주석·따옴표·공백이 섞여도 "
        "같은 404 가 납니다"
    ),
    400: "본문 형식 오류입니다(공식 문서: 400 = 요청 형식 오류). content 2000자 상한을 확인하세요",
}


def _note(out: dict | None, reason: str) -> None:
    """실패 사유를 호출자가 준 sink 에 적는다(주면 적고, 안 주면 아무 일도 없다).

    반환값을 bool 로 유지한 이유: `send_slack`/`send_discord` 의 bool 계약에 기대는
    호출부·테스트가 이미 여러 곳이고, 발송 성공/실패 판단에는 bool 이면 충분하다.
    사유가 필요한 곳은 **진단 엔드포인트 하나**뿐이라 선택적 out 파라미터로 둔다.
    """
    if out is not None:
        out["reason"] = reason


def _post_json(
    url: str, payload: dict, label: str, hints: dict[int, str] | None = None,
    out: dict | None = None,
) -> tuple[int, str] | None:
    """JSON POST 1회. (status, body) 또는 실패 시 None. 예외를 밖으로 던지지 않는다.

    알림 실패가 수집 사이클을 멈추게 하면 안 되므로 전부 삼키고 로그만 남긴다.
    `hints` 는 HTTP 상태 → 조치 안내(선택). 확인된 문구만 넣는다.
    `out` 은 실패 사유 sink(선택) — **비밀을 지운 뒤** 넣는다.
    """
    secrets = url_secrets(url)
    request = urllib.request.Request(
        url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            # 두 채널 모두 Authorization 헤더를 쓰지 않는다(위 모듈 주석의 1차 출처 참고).
            "Content-Type": "application/json;charset=utf-8",
            "User-Agent": _USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", errors="replace").strip()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace").strip()[:300]
        except Exception:
            pass
        retry_after = e.headers.get("Retry-After") if e.headers else None
        suffix = f" (Retry-After={retry_after})" if retry_after else ""
        hint = (hints or {}).get(e.code)
        if hint:
            suffix += f" — {hint}"
        logger.warning("[%s] 발송 실패: HTTP %s / %s%s", label, e.code, body, suffix)
        _note(out, f"HTTP {e.code}: {scrub(body, secrets)}{suffix}".strip())
        return None
    except Exception as e:
        logger.warning("[%s] 발송 실패: %s%s", label, type(e).__name__, _safe_reason(e, url))
        detail = scrub(str(getattr(e, "reason", "") or e), secrets)
        _note(out, f"{type(e).__name__}: {detail}" if detail else type(e).__name__)
        return None


def send_slack(
    text: str, blocks: list[dict] | None = None, *, out: dict | None = None
) -> bool:
    """Slack Incoming Webhook 으로 1건 발송. 성공하면 True.

    `text` 는 blocks 를 쓰더라도 항상 넣는다 — 알림 미리보기·접근성 폴백에 쓰인다.
    `out` 에 dict 를 주면 실패 시 `out["reason"]` 에 비밀을 지운 사유가 담긴다.
    """
    url = slack_webhook_url()
    if url is None:
        _note(out, "SLACK_WEBHOOK_URL 이 없거나 형식 검사에서 거부됐습니다")
        return False

    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    result = _post_json(url, payload, "slack", out=out)
    if result is None:
        return False
    status, body = result
    # 검증된 규격: 성공 = HTTP 200 **AND** 본문 문자열 "ok" (JSON 이 아니다).
    if status == 200 and body == _SLACK_SUCCESS_BODY:
        return True
    logger.warning("[slack] 발송 실패: HTTP %s / %s", status, body[:200])
    _note(out, f"HTTP {status}: {scrub(body, url_secrets(url))}".strip())
    return False


def send_discord(text: str, *, out: dict | None = None) -> bool:
    """Discord Webhook 으로 1건 발송. 성공하면 True.

    `?wait=true` 를 붙이는 이유는 모듈 주석 참고 — 붙이지 않으면 저장되지 않은 메시지도
    오류 없이 204 로 돌아와, "발송 성공 시에만 기준선 이동" 규칙이 그 전환을 영구 유실시킨다.
    `out` 에 dict 를 주면 실패 시 `out["reason"]` 에 비밀을 지운 사유가 담긴다.
    """
    url = discord_webhook_url()
    if url is None:
        _note(out, "DISCORD_WEBHOOK_URL 이 없거나 형식 검사에서 거부됐습니다")
        return False

    # 사용자가 이미 쿼리스트링을 붙여 둔 URL 도 깨지지 않게 병합한다.
    parts = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parts.query))
    query["wait"] = "true"
    target = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(query)))

    payload = {
        "content": text,
        # ★ 멘션을 구조적으로 차단한다. 웹훅 기본값은 {"parse": ["users"]} 라서
        #   종목명에 섞인 유저 멘션이 실제로 핑을 보낸다. 텍스트 이스케이프와 달리
        #   문자 조합으로 우회할 수 없다.
        "allowed_mentions": {"parse": []},
    }

    result = _post_json(target, payload, "discord", _DISCORD_STATUS_HINTS, out=out)
    if result is None:
        return False
    status, body = result
    # wait=true 면 200 + 메시지 JSON. 204 는 wait 가 무시된 경우를 위한 관용 허용.
    if status in (200, 204):
        return True
    logger.warning("[discord] 발송 실패: HTTP %s / %s", status, body[:200])
    _note(out, f"HTTP {status}: {scrub(body, url_secrets(target))}".strip())
    return False


def url_secrets(url: str) -> list[str]:
    """이 URL 에서 비밀로 취급할 조각들 — 호스트 + 마지막 두 경로 조각.

    Discord 는 `/webhooks/{id}/{token}`, Slack 은 `/services/…/B…/{secret}` 이라
    마지막 두 조각이 곧 자격증명이다. 호스트도 넣는 이유는 "어느 서비스로 보내려다
    실패했는가"조차 응답으로 흘리지 않기 위함이다(채널명으로 이미 알 수 있다).

    ★ **경로에서 자른다.** 원본 URL 문자열에서 `rsplit("/")` 하면 Discord 처럼
    쿼리(`?wait=true`)가 붙은 경우 마지막 조각이 `{token}?wait=true` 가 되어 본문에
    등장하는 **맨 토큰과 일치하지 않는다** — 즉 스크러빙이 통과된다. 기존 로그
    스크러빙(`_safe_reason`)이 이 구멍을 갖고 있었고, 사유를 응답에 실으면서
    테스트로 드러났다.
    """
    parts = urllib.parse.urlsplit(url)
    segments = [seg for seg in parts.path.split("/") if seg]
    out = segments[-2:]
    if parts.netloc:
        out.append(parts.netloc)
    return out


def scrub(text: str, secrets: list[str], limit: int = 200) -> str:
    """진단 문구에서 비밀 조각을 **지운다**(문구 전체를 버리지 않는다).

    통째로 버리는 방식(`_safe_reason` 의 기존 정책)은 로그에는 안전하지만 응답으로
    사유를 돌려줄 때는 쓸 수 없다 — 상류가 본문에 URL 을 되돌려주는 순간 사유가
    빈 문자열이 되어 "왜 실패했는지 모른다"로 되돌아간다. 그래서 조각만 마스킹하고
    상태코드·에러코드 같은 진단 가치는 남긴다.

    긴 조각부터 지운다 — 짧은 조각(호스트)을 먼저 지우면 긴 조각(URL 전체) 안의
    부분만 사라져 남은 잔여물이 통과할 수 있다.
    """
    result = text[:limit]
    for secret in sorted(secrets, key=len, reverse=True):
        if secret:
            result = result.replace(secret, "***")
    return result.strip()


def _safe_reason(exc: Exception, url: str) -> str:
    """예외에서 **URL 을 담지 않는** 진단 문구만 뽑아낸다. 없으면 빈 문자열.

    왜 이렇게까지 하나 — 타입 이름만 남기면 로그가 `URLError` 한 단어라서, 사용자가 자기
    네트워크에서 왜 안 가는지 알 방법이 없다(실측: 프록시 차단 환경에서 정확히 그랬다).
    반면 `urllib.error.URLError.reason` 이 OSError 인 경우 그 문자열은 errno/strerror
    기반이라 URL 을 담지 않고 원인을 정확히 알려준다 — 예: "Tunnel connection failed:
    403 Forbidden", "[Errno -2] Name or service not known".

    그래서 **OSError 인 reason 만** 통과시킨다. `URLError("failed to reach https://…")`
    처럼 문자열로 만들어진 reason 은 호출자가 URL 을 넣을 수 있으므로 제외한다.
    마지막으로, 그래도 URL 조각이 섞여 있으면 문구 전체를 버린다(이중 방어).
    """
    reason = getattr(exc, "reason", None)
    if not isinstance(reason, OSError):
        return ""
    text = str(reason)[:200]
    # 비밀 조각 판정은 url_secrets 하나로 모았다 — 쿼리스트링이 붙은 URL 에서 조각을
    # 잘못 자르던 구멍이 여기에도 있었다(그 함수 주석 참고).
    if any(s in text for s in url_secrets(url)):
        return ""
    return f": {text}"


# ────────────────────────────────────────────
# 채널 레지스트리 — 알림 엔진이 채널 목록을 하드코딩하지 않도록
# ────────────────────────────────────────────

@dataclass(frozen=True)
class Channel:
    name: str
    dialect: Dialect
    is_enabled: Callable[[], bool]
    send: Callable[[str], bool]


CHANNEL_NAMES: tuple[str, ...] = ("slack", "discord")


def all_channels() -> tuple[Channel, ...]:
    """전체 웹훅 채널. **모듈 상수가 아니라 함수인 이유가 있다.**

    상수 튜플로 두면 `Channel` 이 import 시점의 함수 객체를 붙잡아서, 나중에
    `alert_channels.slack_enabled` 를 바꿔도(테스트의 monkeypatch 든 런타임 교체든)
    **아무 효과가 없으면서 아무도 실패하지 않는다.** 이 저장소가 반복해서 물린 바로 그
    패턴이다(판정 규칙 3중 복제, 가짜 락 테스트, import 시점에 고정된 diff 기본값).
    호출 시점에 모듈 전역을 다시 읽도록 함수로 둔다.
    """
    return (
        Channel("slack", SLACK_DIALECT, slack_enabled, send_slack),
        Channel("discord", DISCORD_DIALECT, discord_enabled, send_discord),
    )


def enabled_channels() -> tuple[Channel, ...]:
    """설정이 갖춰진 웹훅 채널만. 이메일은 notifier 가 따로 관리한다."""
    return tuple(c for c in all_channels() if c.is_enabled())
