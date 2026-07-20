import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import gspread
from google.oauth2.service_account import Credentials

from config import (
    CREDENTIALS_ENV_KEY,
    SHEET_DASHBOARD,
    SHEET_STOCKDATA,
    STOCK_CODE_LENGTH,
)

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_LOCAL_CREDENTIALS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "mystockbot-497909-4649b1cfee23.json"
)


def _get_client() -> gspread.Client:
    raw = os.environ.get(CREDENTIALS_ENV_KEY)
    if raw:
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        return gspread.authorize(creds)
    return gspread.service_account(filename=_LOCAL_CREDENTIALS_FILE, scopes=_SCOPES)


def load_stock_list(spreadsheet_id: str) -> list[dict]:
    client = _get_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(SHEET_DASHBOARD)
    rows = sheet.get_all_values()

    result = []
    for row in rows[1:]:
        raw_code = str(row[0]).strip() if row else ""
        raw_name = str(row[1]).strip() if len(row) > 1 else ""

        if not raw_code:
            continue

        code = raw_code.zfill(STOCK_CODE_LENGTH).upper()

        if len(code) != STOCK_CODE_LENGTH or not code.isalnum():
            continue

        result.append({"code": code, "name": raw_name})

    return result


def load_stock_data_rows(spreadsheet_id: str) -> list[list]:
    """StockData 워크시트의 데이터 행(헤더 제외)을 읽기 전용으로 반환."""
    client = _get_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(SHEET_STOCKDATA)
    rows = sheet.get_all_values()
    return rows[1:] if rows else []


def write_stock_data(spreadsheet_id: str, rows: list[list]) -> None:
    if not rows:
        return
    client = _get_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(SHEET_STOCKDATA)
    str_rows = [[("" if v is None else str(v)) for v in row] for row in rows]

    existing_values = sheet.get_all_values()
    existing_keys = set()
    if existing_values:
        for row in existing_values[1:]:
            if len(row) >= 2:
                existing_keys.add((row[0], row[1]))

    new_rows = []
    skipped = 0
    for row in str_rows:
        key = (row[0], row[1])
        if key in existing_keys:
            skipped += 1
            continue
        new_rows.append(row)

    if skipped:
        print(f"[sheets] 중복 (날짜,종목코드) {skipped}건 건너뜀")

    if not new_rows:
        return

    sheet.append_rows(new_rows, value_input_option="RAW", table_range="A1")
