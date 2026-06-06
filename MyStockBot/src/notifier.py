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

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465


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
    rows = "".join(
        f"<tr>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{item.get('code', '')}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;'>{item.get('name', '')}</td>"
        f"<td style='padding:6px 12px;border:1px solid #e5e7eb;text-align:right;'>{item.get('close', '')}</td>"
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
          <th style="padding:6px 12px;border:1px solid #e5e7eb;text-align:right;">당일종가</th>
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
        f"<td style='padding:6px 12px;border:1px solid #fca5a5;'>{item.get('code', '')}</td>"
        f"<td style='padding:6px 12px;border:1px solid #fca5a5;'>{item.get('name', '')}</td>"
        f"<td style='padding:6px 12px;border:1px solid #fca5a5;color:#dc2626;'>{item.get('error', '')}</td>"
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


def send_report(success_list: list[dict], failed_list: list[dict], date_str: str) -> None:
    sender = os.environ.get(SENDER_EMAIL_ENV_KEY, "")
    password = os.environ.get(GMAIL_APP_PASSWORD_ENV_KEY, "")
    recipient_raw = os.environ.get(NOTIFY_EMAIL_ENV_KEY, "")

    recipients = [addr.strip() for addr in recipient_raw.split(",") if addr.strip()]

    if not sender or not password or not recipients:
        print("[notifier] 이메일 환경변수 누락 — 알림 발송 건너뜀")
        return

    subject = _build_subject(success_list, failed_list, date_str)
    html = _build_html(success_list, failed_list, date_str)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as smtp:
            smtp.login(sender, password)
            smtp.sendmail(sender, recipients, msg.as_string())
    except Exception as e:
        print(f"[notifier] 이메일 발송 실패: {e}")
