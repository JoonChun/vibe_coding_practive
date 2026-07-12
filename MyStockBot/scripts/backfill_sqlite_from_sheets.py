import os
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

from dotenv import load_dotenv

load_dotenv(_BASE_DIR / ".env")

import config
import db
import sheets

# config.STOCKDATA_HEADER (한글) 순서와 1:1 대응하는 영문 키
_ROW_KEYS = [
    "date", "code", "name",
    "open", "close", "low", "high", "volume",
    "macd_1d", "rsi_1d", "macd_60m", "rsi_60m",
    "short_view", "long_view",
    "bb_upper", "bb_mid", "bb_lower",
    "per", "pbr", "roe", "revenue", "net_income",
]


def _row_to_item(row: list) -> dict:
    padded = list(row) + [None] * (len(_ROW_KEYS) - len(row))
    values = padded[: len(_ROW_KEYS)]
    return dict(zip(_ROW_KEYS, values))


def _backfill_watchlist(spreadsheet_id: str) -> None:
    stock_list = sheets.load_stock_list(spreadsheet_id)
    print(f"[backfill] Dashboard 종목 {len(stock_list)}건 로드")

    added = 0
    for stock in stock_list:
        try:
            db.add_watchlist_item(stock["code"], stock["name"])
            added += 1
        except db.DuplicateError:
            pass
        except Exception as e:
            print(f"[backfill] 종목 등록 실패 ({stock.get('code')}): {e}")

    print(f"[backfill] watchlist 신규 등록 {added}건")


def _backfill_bar_history(spreadsheet_id: str) -> None:
    rows = sheets.load_stock_data_rows(spreadsheet_id)
    print(f"[backfill] StockData 행 {len(rows)}건 로드")

    by_date: dict[str, list[dict]] = {}
    for row in rows:
        if not row or not row[0]:
            continue
        item = _row_to_item(row)
        date_str = item["date"]
        by_date.setdefault(date_str, []).append(item)

    total_inserted = 0
    for date_str, items in by_date.items():
        inserted = db.save_daily_bars(date_str, items)
        total_inserted += inserted
        print(f"[backfill] {date_str}: {inserted}건 저장")

    print(f"[backfill] bar_history 총 {total_inserted}건 저장")


def main() -> None:
    db.init_db()

    spreadsheet_id = os.environ.get(config.SPREADSHEET_ID_ENV_KEY)
    if not spreadsheet_id:
        print(f"[backfill] 환경변수 {config.SPREADSHEET_ID_ENV_KEY} 가 설정되지 않았습니다.")
        sys.exit(1)

    _backfill_watchlist(spreadsheet_id)
    _backfill_bar_history(spreadsheet_id)


if __name__ == "__main__":
    main()
