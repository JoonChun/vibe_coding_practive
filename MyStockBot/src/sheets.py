import json
import logging
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

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

_LOCAL_CREDENTIALS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "mystockbot-497909-4649b1cfee23.json"
)

# Dashboard C열에 이 표시가 있으면 수집 대상에서 제외한다(웹앱에서 관심종목을 삭제했을 때
# 시트 행을 지우는 대신 이 표시를 남긴다 — 사용자가 직접 넣은 행을 파괴하지 않고, 셀만
# 비우면 되돌릴 수 있다). 대소문자·공백은 무시하고 비교한다.
DASHBOARD_INACTIVE_MARK = "해제"
_DASHBOARD_CODE_COL = 1  # A열
_DASHBOARD_NAME_COL = 2  # B열
_DASHBOARD_STATUS_COL = 3  # C열


def credentials_available() -> bool:
    """Google 자격증명이 준비돼 있는지(환경변수 JSON 또는 로컬 키파일). 호출 없이 판단."""
    if os.environ.get(CREDENTIALS_ENV_KEY):
        return True
    return os.path.isfile(_LOCAL_CREDENTIALS_FILE)


def _get_client() -> gspread.Client:
    raw = os.environ.get(CREDENTIALS_ENV_KEY)
    if raw:
        info = json.loads(raw)
        creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
        return gspread.authorize(creds)
    return gspread.service_account(filename=_LOCAL_CREDENTIALS_FILE, scopes=_SCOPES)


def _dashboard_ws(spreadsheet_id: str):
    return _get_client().open_by_key(spreadsheet_id).worksheet(SHEET_DASHBOARD)


def _is_inactive_mark(value) -> bool:
    return str(value or "").strip().casefold() == DASHBOARD_INACTIVE_MARK.casefold()


def _parse_dashboard_rows(rows: list[list]) -> list[dict]:
    """Dashboard 원시 행 → [{code, name, inactive, row_number}] (헤더 제외, 유효 코드만)."""
    parsed = []
    for offset, row in enumerate(rows[1:], start=2):  # 2행부터(1행=헤더)
        raw_code = str(row[0]).strip() if row else ""
        raw_name = str(row[1]).strip() if len(row) > 1 else ""
        raw_status = row[2] if len(row) > 2 else ""

        if not raw_code:
            continue

        code = raw_code.zfill(STOCK_CODE_LENGTH).upper()
        if len(code) != STOCK_CODE_LENGTH or not code.isalnum():
            continue

        parsed.append({
            "code": code,
            "name": raw_name,
            "inactive": _is_inactive_mark(raw_status),
            "row_number": offset,
        })
    return parsed


def load_dashboard_entries(spreadsheet_id: str) -> list[dict]:
    """Dashboard 전체 항목(해제 표시분 포함). 동기화용 — 행 번호·해제 여부까지 필요할 때."""
    return _parse_dashboard_rows(_dashboard_ws(spreadsheet_id).get_all_values())


def load_stock_list(spreadsheet_id: str) -> list[dict]:
    """수집 대상 종목 목록. C열에 '해제' 표시가 있는 행은 제외한다."""
    return [
        {"code": entry["code"], "name": entry["name"]}
        for entry in load_dashboard_entries(spreadsheet_id)
        if not entry["inactive"]
    ]


def upsert_dashboard_item(spreadsheet_id: str, code: str, name: str) -> str:
    """Dashboard 에 종목을 등록(멱등). 이미 있으면 '해제' 표시만 지우고 이름을 보정한다.

    반환: "appended" | "reactivated" | "unchanged".
    값(Value)만 쓰므로 시트에 지정해 둔 서식은 건드리지 않는다(PRD §7 디자인 가이드).
    """
    ws = _dashboard_ws(spreadsheet_id)
    entries = _parse_dashboard_rows(ws.get_all_values())
    existing = next((e for e in entries if e["code"] == code), None)

    if existing is None:
        ws.append_row([code, name, ""], value_input_option="RAW", table_range="A1")
        return "appended"

    updates = []
    if existing["inactive"]:
        updates.append({"row": existing["row_number"], "col": _DASHBOARD_STATUS_COL, "value": ""})
    if name and existing["name"] != name:
        updates.append({"row": existing["row_number"], "col": _DASHBOARD_NAME_COL, "value": name})

    for u in updates:
        ws.update_cell(u["row"], u["col"], u["value"])

    if not updates:
        return "unchanged"
    return "reactivated" if existing["inactive"] else "unchanged"


def deactivate_dashboard_item(spreadsheet_id: str, code: str) -> bool:
    """Dashboard 에서 해당 종목을 수집 대상에서 제외(C열에 '해제' 표시).

    행을 삭제하지 않는다 — 사용자가 직접 입력한 데이터를 파괴하지 않고, C열만 비우면
    되돌릴 수 있다. 해당 코드가 없거나 이미 해제 상태면 False.
    """
    ws = _dashboard_ws(spreadsheet_id)
    entries = _parse_dashboard_rows(ws.get_all_values())
    target = next((e for e in entries if e["code"] == code and not e["inactive"]), None)
    if target is None:
        return False
    ws.update_cell(target["row_number"], _DASHBOARD_STATUS_COL, DASHBOARD_INACTIVE_MARK)
    return True


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
        logger.info(f"[sheets] 중복 (날짜,종목코드) {skipped}건 건너뜀")

    if not new_rows:
        return

    sheet.append_rows(new_rows, value_input_option="RAW", table_range="A1")
