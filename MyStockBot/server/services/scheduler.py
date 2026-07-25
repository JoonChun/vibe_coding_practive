"""일일 배치 잡 — 종목마스터 갱신 + 관심종목 시트→앱 임포트.

스냅샷 수집·bar_history 저장은 더 이상 이 스케줄러가 하지 않는다
(collector.py 의 상시 수집 루프가 대체 — server/services/collector.py 참고).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

import stock_master
import watchlist_sync
from config import TIMEZONE

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone=TIMEZONE)


def _daily_master_refresh() -> None:
    date_str = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d")
    logger.info("[scheduler] 종목마스터 일일 갱신 시작 (%s)", date_str)
    try:
        stock_master.refresh_stock_master()
    except Exception as e:
        logger.warning("[scheduler] 종목마스터 갱신 실패: %s", e)


def _watchlist_sheet_import() -> None:
    """시트 Dashboard 에 직접 추가된 종목을 앱 관심종목으로 끌어온다(추가 전용).

    크론 배치(KST 16:00)보다 앞선 시각에 돌려 두 목록이 그날 수집 전에 수렴하도록 한다.
    """
    if not watchlist_sync.is_enabled():
        return
    try:
        watchlist_sync.import_from_sheet()
    except Exception as e:
        logger.warning("[scheduler] 관심종목 시트 임포트 실패: %s", e)


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
    # 크론 배치(KST 16:00)가 시트를 읽기 전에 앱→시트/시트→앱을 수렴시킨다.
    _scheduler.add_job(
        _watchlist_sheet_import,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute=50,
        timezone=TIMEZONE,
        id="watchlist_sheet_import",
        replace_existing=True,
    )
    _scheduler.start()


def shutdown() -> None:
    _scheduler.shutdown()
