import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

from dotenv import load_dotenv

load_dotenv(_BASE_DIR / ".env")

import config
import db
import sheets

# 엔트리포인트가 로깅 설정을 책임진다(모듈들은 getLogger 만 사용).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

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
    logger.info(f"[backfill] Dashboard 종목 {len(stock_list)}건 로드")

    added = 0
    for stock in stock_list:
        try:
            db.add_watchlist_item(stock["code"], stock["name"])
            added += 1
        except db.DuplicateError:
            pass
        except Exception as e:
            logger.warning(f"[backfill] 종목 등록 실패 ({stock.get('code')}): {e}")

    logger.info(f"[backfill] watchlist 신규 등록 {added}건")


def _to_epoch(date_str) -> int | None:
    """시트 날짜(YYYY-MM-DD / YYYYMMDD 등)를 KST 자정 기준 Unix epoch(초)로. 실패 시 None.

    candles 서비스(_kst_midnight_epoch)와 동일 기준이라, 백필한 일봉이 서버가 KIS/yfinance
    로 수집하는 일봉과 같은 t 키로 자연히 병합된다.
    """
    digits = "".join(ch for ch in str(date_str) if ch.isdigit())[:8]
    if len(digits) != 8:
        return None
    try:
        dt = datetime.strptime(digits, "%Y%m%d").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return int(dt.timestamp())
    except ValueError:
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _backfill_candles(spreadsheet_id: str) -> None:
    """시트 StockData(일봉 스냅샷)를 앱이 실제로 읽는 candles(tf='1d') 저장소로 적재한다.

    데이터 소유 경계: 구글 시트 = 크론 리포트, SQLite candles = 웹앱 조회 소스.
    (과거엔 고아 bar_history 테이블에 넣었으나 서버가 읽지 않아 死데이터였다 → candles 로 연결.)
    """
    rows = sheets.load_stock_data_rows(spreadsheet_id)
    logger.info(f"[backfill] StockData 행 {len(rows)}건 로드")

    by_code: dict[str, list[dict]] = {}
    for row in rows:
        if not row or not row[0]:
            continue
        item = _row_to_item(row)
        code = item.get("code")
        t = _to_epoch(item.get("date"))
        close = _num(item.get("close"))
        if not code or t is None or close is None:
            continue
        vol = _num(item.get("volume"))
        by_code.setdefault(db.normalize_code(code), []).append({
            "t": t,
            "open": _num(item.get("open")),
            "high": _num(item.get("high")),
            "low": _num(item.get("low")),
            "close": close,
            "volume": int(vol) if vol is not None else None,
        })

    total = 0
    for code, items in by_code.items():
        items.sort(key=lambda x: x["t"])
        total += db.upsert_candles(code, "1d", items)
        logger.info(f"[backfill] {code}: 일봉 {len(items)}건 → candles(1d)")

    logger.info(f"[backfill] candles(1d) 총 {total}건 저장")


def main() -> None:
    db.init_db()

    spreadsheet_id = os.environ.get(config.SPREADSHEET_ID_ENV_KEY)
    if not spreadsheet_id:
        logger.warning(f"[backfill] 환경변수 {config.SPREADSHEET_ID_ENV_KEY} 가 설정되지 않았습니다.")
        sys.exit(1)

    _backfill_watchlist(spreadsheet_id)
    _backfill_candles(spreadsheet_id)


if __name__ == "__main__":
    main()
