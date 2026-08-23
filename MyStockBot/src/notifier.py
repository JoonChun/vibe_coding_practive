import html
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz

from config import (
    GMAIL_APP_PASSWORD_ENV_KEY,
    NOTIFY_EMAIL_ENV_KEY,
    SENDER_EMAIL_ENV_KEY,
    TIMEZONE,
)

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465
# ★ 타임아웃 필수. smtplib 은 기본값이 소켓 전역 타임아웃(보통 None = 무한)이라,
#   지정하지 않으면 SMTP 연결이 응답하지 않을 때 호출 스레드가 **영구히** 멈춘다.
#   이 함수는 크론 배치와 수집 루프(알림 발송) 양쪽에서 불리므로 둘 다 같이 멈춘다.
SMTP_TIMEOUT_SECONDS = 30


def esc(value) -> str:
    """HTML 이스케이프. 종목명·에러 메시지는 외부(시트·API·예외)에서 오므로 그대로 넣지 않는다."""
    return html.escape("" if value is None else str(value), quote=True)


def _build_subject(success_list: list[dict], failed_list: list[dict], date_str: str) -> str:
    if failed_list and not success_list:
        return f"[오류 발생] MyStockBot 수집 실패 - {date_str}"
    if failed_list:
        return f"[일부 오류] MyStockBot 수집 결과 - {date_str}"
    return f"[성공] MyStockBot 주가 수집 완료 - {date_str}"


def _build_summary_html(success_list: list[dict], failed_list: list[dict]) -> str:
    success_color = "#16a34a"
    fail_color = "#dc2626"
    parts = []
    if success_list:
        parts.append(
            f'<span style="color:{success_color};font-weight:bold;">성공 {len(success_list)}종목</span>'
        )
    if failed_list:
        parts.append(
            f'<span style="color:{fail_color};font-weight:bold;">실패 {len(failed_list)}종목</span>'
        )
    return " &nbsp;/&nbsp; ".join(parts)


def _build_success_table(success_list: list[dict]) -> str:
    if not success_list:
        return ""
    # 기준일(bar_date) = 그 종가가 실제로 속한 거래일. 실행일과 다르면(휴장일 실행 등)
    # 한눈에 보이도록 별도 컬럼으로 노출한다 — "오늘 종가"로 오해하지 않도록.
    rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{esc(item.get('code', ''))}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{esc(item.get('name', ''))}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{esc(item.get('bar_date') or '—')}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;text-align:right;'>"
        f"{esc(item.get('close', ''))}</td>"
        f"</tr>"
        for item in success_list
    )
    return f"""
    <h3 style="color:#16a34a;margin-top:24px;">성공 종목</h3>
    <table style="border-collapse:collapse;width:100%;font-size:14px;">
      <thead>
        <tr style="background:#f0fdf4;">
          <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">종목코드</th>
          <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">종목명</th>
          <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:left;">기준일</th>
          <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:right;">종가</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _build_failed_table(failed_list: list[dict]) -> str:
    if not failed_list:
        return ""
    rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border:1px solid #fca5a5;'>{esc(item.get('code', ''))}</td>"
        f"<td style='padding:6px 12px;border:1px solid #fca5a5;'>{esc(item.get('name', ''))}</td>"
        f"<td style='padding:6px 12px;border:1px solid #fca5a5;color:#dc2626;'>"
        f"{esc(item.get('error', ''))}</td>"
        f"</tr>"
        for item in failed_list
    )
    return f"""
    <h3 style="color:#dc2626;margin-top:24px;">실패 종목</h3>
    <table style="border-collapse:collapse;width:100%;font-size:14px;border:2px solid #dc2626;">
      <thead>
        <tr style="background:#fef2f2;">
          <th style="padding:6px 12px;border:1px solid #fca5a5;text-align:left;">종목코드</th>
          <th style="padding:6px 12px;border:1px solid #fca5a5;text-align:left;">종목명</th>
          <th style="padding:6px 12px;border:1px solid #fca5a5;text-align:left;">에러 원인</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """


def _build_html(success_list: list[dict], failed_list: list[dict], date_str: str) -> str:
    summary = _build_summary_html(success_list, failed_list)
    success_table = _build_success_table(success_list)
    failed_table = _build_failed_table(failed_list)
    now_str = datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S %Z")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;max-width:640px;margin:0 auto;padding:24px;color:#111827;">
  <h2 style="margin-bottom:4px;">MyStockBot 수집 결과</h2>
  <p style="color:#6b7280;margin-top:0;">{date_str}</p>
  <div style="padding:12px 16px;background:#f9fafb;border-radius:6px;font-size:15px;">
    {summary}
  </div>
  {success_table}
  {failed_table}
  <p style="margin-top:32px;font-size:12px;color:#9ca3af;">작성 시각: {now_str}</p>
</body>
</html>"""


def _email_config() -> tuple[str, str, list[str]] | None:
    """(sender, password, recipients). 하나라도 비면 None."""
    sender = os.environ.get(SENDER_EMAIL_ENV_KEY, "").strip()
    password = os.environ.get(GMAIL_APP_PASSWORD_ENV_KEY, "").strip()
    recipients = [
        addr.strip()
        for addr in os.environ.get(NOTIFY_EMAIL_ENV_KEY, "").split(",")
        if addr.strip()
    ]
    if not sender or not password or not recipients:
        return None
    return sender, password, recipients


def email_enabled() -> bool:
    """Gmail 발송이 설정되어 있는지. 알림 채널 선택에 쓴다."""
    return _email_config() is not None


def send_html(subject: str, body_html: str, *, out: dict | None = None) -> bool:
    """HTML 본문 메일 1건 발송. 성공하면 True.

    반환값이 있어야 하는 이유: 판정 전환 알림은 **발송이 성공했을 때만** 기준선을
    갱신한다. 실패를 성공으로 착각해 기준선을 옮기면 그 전환은 영구히 유실된다.

    `out` 에 dict 를 주면 실패 시 `out["reason"]` 에 사유가 담긴다(진단 엔드포인트용).
    **앱 비밀번호는 지운다** — 사유는 API 응답으로 나가고 화면에 표시된다.
    """
    config = _email_config()
    if config is None:
        logger.warning("[notifier] 이메일 환경변수 누락 — 알림 발송 건너뜀")
        if out is not None:
            out["reason"] = (
                "SENDER_EMAIL · GMAIL_APP_PASSWORD · NOTIFY_EMAIL 환경변수가 누락됐습니다"
            )
        return False
    sender, password, recipients = config

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL(
            GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, recipients, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError as e:
        # 실측(2026-08-23): Gmail 이 535 / "5.7.8 Username and Password not accepted"
        # + 지원 문서 링크를 돌려줬다. 원문이 영어 두 줄이라 바로 읽기 어려워 **Google 이
        # 준 문장을 다시 말하는 수준의** 한 줄 요약만 앞에 붙인다.
        #
        # 원인 목록(2단계 인증 필요 여부 등)은 넣지 않는다 — 이 저장소는 외부 스펙을
        # 1차 출처로만 적고, Google 지원 문서는 개발 환경에서 403 으로 차단돼 확인할 수
        # 없었다. 확인 못 한 정책을 단정하면 사용자를 엉뚱한 곳으로 보낸다. 응답에 들어
        # 있는 Google 링크를 그대로 남겨 사용자가 1차 출처로 가게 한다.
        logger.warning(f"[notifier] 이메일 발송 실패: {e}")
        if out is not None:
            detail = str(e)[:300]
            for secret in (password, password.replace(" ", "")):
                if secret:
                    detail = detail.replace(secret, "***")
            out["reason"] = (
                f"Google 이 자격증명을 거부했습니다(SMTP 535) — {detail}"
            )
        return False
    except Exception as e:
        logger.warning(f"[notifier] 이메일 발송 실패: {e}")
        if out is not None:
            # 앱 비밀번호를 지운다. 공백 있는 형태("abcd efgh …")와 없는 형태 둘 다
            # — Gmail 은 표시할 때 공백을 넣고 사용자는 그대로 붙여넣는 경우가 있다.
            detail = str(e)[:200]
            for secret in (password, password.replace(" ", "")):
                if secret:
                    detail = detail.replace(secret, "***")
            out["reason"] = f"{type(e).__name__}: {detail}".strip()
        return False


def send_report(success_list: list[dict], failed_list: list[dict], date_str: str) -> bool:
    return send_html(
        _build_subject(success_list, failed_list, date_str),
        _build_html(success_list, failed_list, date_str),
    )
