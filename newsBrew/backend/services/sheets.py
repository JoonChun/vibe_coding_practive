import asyncio
import json
import gspread
from google.oauth2.service_account import Credentials
from services.ai_brewer import BrewedArticle

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]


def _sync_archive_to_sheets(
    service_account_json: str,
    sheet_id: str,
    brew_date: str,
    keyword_results: dict[str, list[BrewedArticle]],
) -> None:
    try:
        creds_data = json.loads(service_account_json)
    except json.JSONDecodeError:
        raise ValueError("서비스 계정 JSON 형식이 올바르지 않습니다.")

    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    gc = gspread.authorize(creds)

    try:
        spreadsheet = gc.open_by_key(sheet_id)
    except gspread.exceptions.APIError as e:
        status = e.response.status_code if hasattr(e, 'response') else 0
        if status == 404:
            raise ValueError(
                f"스프레드시트를 찾을 수 없습니다 (Sheet ID: {sheet_id}). "
                "ID가 맞는지 확인하고, 서비스 계정 이메일을 시트에 편집자로 공유했는지 확인하세요. "
                f"서비스 계정: {creds_data.get('client_email', '?')}"
            )
        raise

    try:
        worksheet = spreadsheet.worksheet("뉴스 아카이브")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title="뉴스 아카이브", rows="1000", cols="8")
        worksheet.append_row(["날짜", "키워드", "제목", "출처", "발행일", "링크", "요약", "중요도"])

    rows = []
    for keyword, articles in keyword_results.items():
        for a in articles:
            rows.append([
                brew_date, keyword, a.title, a.source,
                a.published_at, a.url, a.summary, a.importance_score
            ])

    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")


async def archive_to_sheets(
    service_account_json: str,
    sheet_id: str,
    brew_date: str,
    keyword_results: dict[str, list[BrewedArticle]],
) -> None:
    if not service_account_json or not sheet_id:
        return

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _sync_archive_to_sheets,
        service_account_json,
        sheet_id,
        brew_date,
        keyword_results,
    )
