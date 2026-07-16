"""일일 배치 잡 — 종목마스터(KOSPI/KOSDAQ) 갱신 전용.

스냅샷 수집·bar_history 저장은 더 이상 이 스케줄러가 하지 않는다
(collector.py 의 상시 수집 루프가 대체 — server/services/collector.py 참고).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

import stock_master
from config import TIMEZONE

_scheduler = BackgroundScheduler(timezone=TIMEZONE)


def _daily_master_refresh() -> None:
    date_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    print(f"[scheduler] 종목마스터 일일 갱신 시작 ({date_str})")
    try:
        stock_master.refresh_stock_master()
    except Exception as e:
        print(f"[scheduler] 종목마스터 갱신 실패: {e}")


def start() -> None:
    _scheduler.add_job(
        _daily_master_refresh,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=0,
        timezone=TIMEZONE,
        id="daily_master_refresh",
        replace_existing=True,
    )
    _scheduler.start()


def shutdown() -> None:
    _scheduler.shutdown()
