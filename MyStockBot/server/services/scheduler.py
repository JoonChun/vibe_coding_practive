from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

import db
import pipeline
from config import TIMEZONE

_scheduler = BackgroundScheduler(timezone=TIMEZONE)


def _daily_load() -> None:
    # always-on 서버가 SQLite의 주인 — 관심종목은 웹앱이 관리하는 SQLite watchlist에서 로드.
    # (옵션 A는 GitHub Actions cron에만 적용되며, 이 스케줄러는 서버 내부이므로 SQLite를 읽는 것이 정상)
    date_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    print(f"[scheduler] 일일 수집 시작 ({date_str})")
    try:
        stock_list = db.load_watchlist()
        if not stock_list:
            print("[scheduler] watchlist 비어 있음 — 수집 건너뜀")
            return
        success, failed = pipeline.collect_snapshots(stock_list)
        saved = db.save_daily_bars(date_str, success)
        print(f"[scheduler] 일일 수집 완료: 성공 {len(success)}건 실패 {len(failed)}건 저장 {saved}건")
    except Exception as e:
        print(f"[scheduler] 일일 수집 실패 ({date_str}): {e}")


def start() -> None:
    _scheduler.add_job(
        _daily_load,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=0,
        timezone=TIMEZONE,
        id="daily_load",
        replace_existing=True,
    )
    _scheduler.start()


def shutdown() -> None:
    _scheduler.shutdown()
