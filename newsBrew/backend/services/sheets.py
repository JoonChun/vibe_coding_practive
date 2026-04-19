import json
import gspread
from google.oauth2.service_account import Credentials
from services.ai_brewer import BrewedArticle

SCOPES = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]


def _get_worksheet(service_account_json: str, sheet_id: str, tab_name: str):
    creds_data = json.loads(service_account_json)
    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_key(sheet_id)
    try:
        worksheet = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="8")
        worksheet.append_row(["날짜", "키워드", "제목", "출처", "발행일", "링크", "요약", "중요도"])
    return worksheet


async def archive_to_sheets(
    service_account_json: str,
    sheet_id: str,
    brew_date: str,
    keyword_results: dict[str, list[BrewedArticle]],
):
    if not service_account_json or not sheet_id:
        return

    worksheet = _get_worksheet(service_account_json, sheet_id, "뉴스 아카이브")
    rows = []
    for keyword, articles in keyword_results.items():
        for a in articles:
            rows.append([
                brew_date, keyword, a.title, a.source,
                a.published_at, a.url, a.summary, a.importance_score
            ])

    if rows:
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")
