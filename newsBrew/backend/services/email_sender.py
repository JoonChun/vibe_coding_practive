import resend
from services.ai_brewer import BrewedArticle


def _build_html(brew_date: str, keyword_results: dict[str, list[BrewedArticle]]) -> str:
    sections = ""
    for keyword, articles in keyword_results.items():
        if not articles:
            continue
        items_html = "".join(
            f"""<li style="margin-bottom:12px;">
                <a href="{a.url}" style="color:#4B3621;font-weight:bold;text-decoration:none;">{a.title}</a>
                <span style="color:#888;font-size:12px;margin-left:8px;">[{a.source}]</span>
                <p style="margin:4px 0;color:#333;font-size:14px;">{a.summary}</p>
            </li>"""
            for a in articles
        )
        sections += f"""
        <h2 style="color:#4B3621;border-bottom:2px solid #FF8C00;padding-bottom:4px;">☕ {keyword}</h2>
        <ul style="padding-left:20px;">{items_html}</ul>
        """

    return f"""
    <div style="font-family:'Pretendard',sans-serif;max-width:700px;margin:auto;background:#F5F5DC;padding:32px;">
        <h1 style="color:#4B3621;">☕ News Brew — {brew_date}</h1>
        {sections}
        <hr style="border:none;border-top:1px solid #ccc;margin:24px 0;">
        <p style="color:#888;font-size:12px;">
            본 메일은 AI가 요약한 내용으로, 원문과 다를 수 있습니다. 반드시 원문 링크를 확인하세요.
        </p>
    </div>
    """


async def send_brew_email(
    api_key: str,
    recipient_emails: str,
    brew_date: str,
    keyword_results: dict[str, list[BrewedArticle]],
    max_retries: int = 3,
) -> bool:
    resend.api_key = api_key
    recipients = [e.strip() for e in recipient_emails.split(",") if e.strip()]
    html_content = _build_html(brew_date, keyword_results)

    for attempt in range(max_retries):
        try:
            resend.Emails.send({
                "from": "News Brew <onboarding@resend.dev>",
                "to": recipients,
                "subject": f"☕ News Brew 리포트 — {brew_date}",
                "html": html_content,
            })
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
    return False
