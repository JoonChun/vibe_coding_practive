"""일일 배치 잡 — 종목마스터 갱신 + 관심종목 시트→앱 임포트.

스냅샷 수집·bar_history 저장은 더 이상 이 스케줄러가 하지 않는다
(collector.py 의 상시 수집 루프가 대체 — server/services/collector.py 참고).
"""
import logging
from datetime import datetime, timezone
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


def refresh_market_holidays(force: bool = False) -> dict:
    """KIS 국내휴장일조회(CTCA0903R) 결과를 SQLite 캐시에 갱신한다.

    ★ 공식 문서가 "가급적 1일 1회 호출"을 요청하므로, 마지막 조회로부터
    KIS_HOLIDAY_MIN_REFRESH_HOURS(기본 20시간)가 지나지 않았으면 **호출하지 않는다.**
    하루 1회 스케줄과 부팅 시 1회가 겹쳐도 실제 호출은 하루 한 번으로 수렴한다.

    반환: {"called": bool, "saved": int, "reason": str}
    """
    import crawler
    import db
    import kis_auth
    from config import KIS_HOLIDAY_LOOKAHEAD_DAYS, KIS_HOLIDAY_MIN_REFRESH_HOURS

    meta = db.get_market_holiday_meta()
    fetched_at = meta.get("fetched_at")
    if not force and fetched_at:
        try:
            last = datetime.strptime(fetched_at, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
            if age_hours < KIS_HOLIDAY_MIN_REFRESH_HOURS:
                return {
                    "called": False, "saved": 0,
                    "reason": f"마지막 조회 {age_hours:.1f}시간 전 — 1일 1회 제한으로 건너뜀",
                }
        except ValueError:
            pass  # 타임스탬프가 깨졌으면 그냥 갱신한다

    try:
        token = kis_auth.get_token()
    except Exception as e:
        return {"called": False, "saved": 0, "reason": f"KIS 자격증명 없음/토큰 실패: {e}"}

    bass_dt = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y%m%d")
    rows = crawler.fetch_kis_holidays(token, bass_dt, KIS_HOLIDAY_LOOKAHEAD_DAYS)
    if not rows:
        return {"called": True, "saved": 0, "reason": "조회 결과 없음(기존 캐시 유지)"}

    saved = db.upsert_market_holidays(rows)
    logger.info(
        "[scheduler] 휴장일 캐시 갱신: %d건 (%s ~ %s)",
        saved, rows[0]["date"], rows[-1]["date"],
    )
    return {"called": True, "saved": saved, "reason": "갱신 완료"}


def _daily_holiday_refresh() -> None:
    try:
        result = refresh_market_holidays()
        if not result["called"]:
            logger.info("[scheduler] 휴장일 갱신 건너뜀: %s", result["reason"])
    except Exception as e:
        logger.warning("[scheduler] 휴장일 갱신 실패: %s", e)


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


def _daily_candle_backfill() -> None:
    """관심종목 전체의 일/주/월봉 과거 이력 백필 — 장 마감 후 1회.

    온디맨드 딥 수집(첫 차트 로딩 수 초)을 예방하고, 상장 이력이 요청보다 짧은 종목도
    candles 쪽 바닥(_history_floor) 기억이 채워져 낮 시간 반복 수집이 사라진다.
    kis_throttle(전역 0.5초 간격)이 호출 속도를 묶으므로 야간 배치로만 돌린다.
    """
    import db

    from . import candles

    rows = db.load_watchlist()
    logger.info("[scheduler] 캔들 백필 시작 — 관심종목 %d개", len(rows))
    for row in rows:
        candles.backfill_history(row["code"])
    logger.info("[scheduler] 캔들 백필 완료")


def _daily_db_backup() -> None:
    """SQLite 일일 백업 — 관심종목·모의투자·알림 기준선이 전부 이 파일 하나에 있다.
    디스크가 같이 죽는 시나리오까지는 못 막지만(오프사이트는 사용자 몫 — DEPLOY.md),
    실수 삭제·파일 손상·마이그레이션 사고는 이걸로 되돌린다."""
    import db

    try:
        path = db.create_backup()
        if path:
            logger.info("[scheduler] DB 백업 완료: %s", path)
        else:
            logger.warning("[scheduler] DB 백업 건너뜀 — 원본 DB 파일이 없음")
    except Exception as e:
        logger.warning("[scheduler] DB 백업 실패: %s", e)


def start() -> None:
    # DB 백업은 주말 포함 매일 — 모의투자·관심종목 편집은 장중이 아니어도 일어난다.
    _scheduler.add_job(
        _daily_db_backup,
        trigger="cron",
        hour=17,
        minute=0,
        timezone=TIMEZONE,
        id="daily_db_backup",
        replace_existing=True,
    )
    _scheduler.add_job(
        _daily_candle_backfill,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=20,
        timezone=TIMEZONE,
        id="daily_candle_backfill",
        replace_existing=True,
    )
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
    # 휴장일 캐시 — 장 시작 전에 하루 1회. 함수 자체가 20시간 제한을 다시 확인하므로
    # 재시작이 잦아도 실제 호출은 하루 한 번으로 수렴한다(공식 "1일 1회" 요청 준수).
    _scheduler.add_job(
        _daily_holiday_refresh,
        trigger="cron",
        hour=8,
        minute=10,
        timezone=TIMEZONE,
        id="daily_holiday_refresh",
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
