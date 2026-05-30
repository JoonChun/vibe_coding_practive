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
    SPREADSHEET_ID_ENV_KEY,
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

        code = raw_code.zfill(STOCK_CODE_LENGTH)

        if len(code) != STOCK_CODE_LENGTH or not code.isdigit():
            continue

        result.append({"code": code, "name": raw_name})

    return result


def write_stock_data(spreadsheet_id: str, rows: list[list]) -> None:
    if not rows:
        return
    client = _get_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(SHEET_STOCKDATA)
    str_rows = [[("" if v is None else str(v)) for v in row] for row in rows]
    sheet.append_rows(str_rows, value_input_option="RAW", table_range="A1")
