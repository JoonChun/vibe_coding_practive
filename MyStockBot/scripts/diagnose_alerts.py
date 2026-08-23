#!/usr/bin/env python3
"""알림 설정 진단 — 서버를 띄우지 않고 `.env` 만 보고 원인을 짚는다.

## 사용
    python3 scripts/diagnose_alerts.py            # 형식 검사만(네트워크 안 탐)
    python3 scripts/diagnose_alerts.py --probe    # 실제로 발송까지 시도

## 왜 있나
알림이 안 갈 때 원인을 찾는 경로가 지금까지 셋 다 불편했다:
  · 서버 로그 — 서버가 다른 터미널의 포그라운드 프로세스면 닿지 못한다(실제로 그랬다).
  · `POST /api/alerts/test` — 서버 기동 + 토큰 찾기 + curl, 세 단계다.
  · `.env` 육안 확인 — 접두사 중복 같은 오염은 눈으로 안 보인다(실제로 못 찾았다).
이 스크립트는 한 줄로 끝난다.

## ★ 출력에 비밀이 없다
이 도구의 존재 이유는 **결과를 그대로 붙여넣어 공유할 수 있다는 것**이다. 웹훅 URL과
앱 비밀번호는 그 자체가 자격증명이므로 출력하지 않는다. 대신 "내가 넣은 그 값인지"를
확인할 수 있게 **길이와 sha256 앞 12자**만 보여준다. `tests/test_diagnose_alerts_script.py`
가 값 자체·긴 불투명 문자열이 새지 않는 것을 적대적으로 검사한다.

## 환경변수 (테스트용)
  MYSTOCKBOT_DIAGNOSE_SKIP_DOTENV=1   `.env` 를 읽지 않는다(os.environ 만 사용)
  MYSTOCKBOT_DIAGNOSE_NO_NETWORK=1    --probe 를 무시하고 네트워크를 타지 않는다
"""
import hashlib
import os
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

# `.env` 는 서버와 **같은 방식**으로 읽는다. sed·grep 으로 직접 파싱하면 갈라진다 —
# python-dotenv 는 따옴표 없는 값의 인라인 `# 주석`을 떼고, 이미 셸에 export 된
# 변수를 덮어쓰지 않는다(실측). 그 두 성질이 진단 결과를 바꾼다.
if os.environ.get("MYSTOCKBOT_DIAGNOSE_SKIP_DOTENV") != "1":
    from dotenv import load_dotenv

    load_dotenv(_BASE_DIR / ".env")

import alert_channels  # noqa: E402  (경로 설정 후 import 해야 한다)
import notifier  # noqa: E402

OK = "✓"
BAD = "✗"
MEH = "·"

# Gmail 앱 비밀번호는 16자다(화면에는 4자씩 공백으로 끊어 보여준다).
_APP_PASSWORD_LEN = 16


def fingerprint(value: str) -> str:
    """값을 드러내지 않고 동일성만 확인시킨다 — 길이 + sha256 앞 12자."""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"길이 {len(value)} · sha256 {digest}"


def check_webhook(channel: str, label: str) -> bool:
    """웹훅 채널 하나를 검사. 발송 가능하면 True."""
    env_key = alert_channels.webhook_env_key(channel)
    raw = os.environ.get(env_key, "")
    value = raw.strip()

    if not value:
        print(f"  {MEH} {label}: 미설정 ({env_key} 없음)")
        return False

    print(f"  {MEH} {label}: {fingerprint(value)}")
    if raw != value:
        print("      주의: 값 앞뒤에 공백이 있습니다(자동으로 제거하고 검사했습니다)")

    problem = alert_channels.webhook_problem(channel)
    if problem is not None:
        print(f"  {BAD} {label}: 형식 검사에서 거부 — {problem}")
        print(f"      → {env_key} 를 고치고 서버를 재시작하세요.")
        return False

    print(f"  {OK} {label}: 형식 통과")
    return True


def check_email() -> bool:
    """Gmail 설정 검사. 셋 중 하나만 빠져도 통째로 비활성이다."""
    parts = {
        "SENDER_EMAIL": os.environ.get("SENDER_EMAIL", "").strip(),
        "GMAIL_APP_PASSWORD": os.environ.get("GMAIL_APP_PASSWORD", "").strip(),
        "NOTIFY_EMAIL": os.environ.get("NOTIFY_EMAIL", "").strip(),
    }
    missing = [key for key, value in parts.items() if not value]
    if missing:
        print(f"  {BAD} 이메일: 미설정 — {', '.join(missing)} 가 없습니다")
        print("      → 셋 중 하나만 빠져도 이메일 채널이 통째로 비활성됩니다.")
        return False

    # 주소는 비밀이 아니라 그대로 보여준다(사용자 자신의 주소이고, 오타 확인에 필요하다).
    print(f"  {MEH} 이메일: {parts['SENDER_EMAIL']} → {parts['NOTIFY_EMAIL']}")
    if "@" not in parts["SENDER_EMAIL"] or "@" not in parts["NOTIFY_EMAIL"]:
        print(f"  {BAD} 이메일: 주소에 @ 가 없습니다")
        return False

    # 앱 비밀번호는 길이만 본다.
    compact = parts["GMAIL_APP_PASSWORD"].replace(" ", "")
    if len(compact) != _APP_PASSWORD_LEN:
        print(f"  {BAD} 이메일: 앱 비밀번호가 {len(compact)}자입니다 "
              f"(Gmail 앱 비밀번호는 공백 제외 {_APP_PASSWORD_LEN}자)")
        print("      → 계정 비밀번호가 아니라 '앱 비밀번호'를 발급해 넣어야 합니다.")
        return False
    print(f"  {OK} 이메일: 앱 비밀번호 {_APP_PASSWORD_LEN}자 확인 "
          f"({fingerprint(compact)})")

    if not notifier.email_enabled():
        # 위 검사를 다 통과했는데 여기서 걸리면 서버가 읽는 경로와 어긋난 것이다.
        print(f"  {BAD} 이메일: notifier 가 비활성으로 판단했습니다(설정 경로 불일치)")
        return False
    return True


def probe(channel_ready: dict[str, bool]) -> None:
    """실제 발송을 시도해 사유를 출력한다. 비밀은 지운 상태로만 나온다."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from config import TIMEZONE
    from server.services import alerts

    sample = alerts.Transition(
        code="000000", name="[진단] 발송 확인", kind="long",
        before="관망", after="매수", close=71200.0, change_pct=1.83,
    )
    reasons: dict[str, str] = {}
    results = alerts.dispatch([sample], datetime.now(ZoneInfo(TIMEZONE)), reasons=reasons)
    if not results:
        print("  발송할 채널이 없습니다.")
        return
    for name, ok in results.items():
        if ok:
            print(f"  {OK} {name}: 발송 성공")
        else:
            print(f"  {BAD} {name}: {reasons.get(name, '사유 미확인 — 서버 로그 확인')}")


def main() -> int:
    want_probe = "--probe" in sys.argv
    no_network = os.environ.get("MYSTOCKBOT_DIAGNOSE_NO_NETWORK") == "1"

    print("== 알림 설정 진단 ==")
    print(f"   .env: {_BASE_DIR / '.env'}"
          f"{' (읽지 않음)' if os.environ.get('MYSTOCKBOT_DIAGNOSE_SKIP_DOTENV') == '1' else ''}")
    print()
    print("[1] 채널 설정")
    ready = {
        "discord": check_webhook("discord", "Discord"),
        "slack": check_webhook("slack", "Slack"),
        "email": check_email(),
    }
    print()

    print("[2] 발송 조건")
    enabled = os.environ.get("DECISION_ALERT_ENABLED", "").strip()
    if enabled in ("1", "true", "True", "yes", "on"):
        print(f"  {OK} DECISION_ALERT_ENABLED: 켜짐")
    else:
        print(f"  {MEH} DECISION_ALERT_ENABLED: 꺼짐 — 자동 알림은 나가지 않습니다")
        print("      (테스트 발송과 이 스크립트의 --probe 는 이 플래그를 우회합니다)")
    print()

    print("[3] 실발송")
    if not any(ready.values()):
        print("  발송 가능한 채널이 없습니다 — [1] 을 먼저 고치세요.")
    elif not want_probe:
        print("  건너뜀. 실제로 보내보려면 --probe 를 붙이세요.")
    elif no_network:
        print("  건너뜀 (MYSTOCKBOT_DIAGNOSE_NO_NETWORK=1).")
    else:
        probe(ready)
    print()

    print("이 출력에는 웹훅 URL·앱 비밀번호가 들어 있지 않습니다 — 그대로 공유해도 됩니다.")
    return 0 if any(ready.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
