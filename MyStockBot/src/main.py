import logging
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from datetime import datetime
from zoneinfo import ZoneInfo

from config import SPREADSHEET_ID_ENV_KEY, TIMEZONE
import market_calendar
import pipeline
import sheets
import notifier

# 크론(GitHub Actions) 실행 로그에 타임존·레벨이 남도록 여기서 한 번 설정한다.
# (모듈들은 logging.getLogger(__name__) 만 쓰고 설정은 엔트리포인트가 책임진다.)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    try:
        tz = ZoneInfo(TIMEZONE)
        now = datetime.now(tz=tz)

        # 주말뿐 아니라 KRX 휴장일(설·추석·대체공휴일·노동절 등)도 건너뛴다.
        # 휴장일에 수집하면 직전 거래일 종가를 받게 되는데, 그대로 '오늘' 날짜로 시트에
        # 기록하면 같은 종가가 여러 날짜로 중복되어 추세가 왜곡된다(PRD §8 경고 항목).
        if not market_calendar.is_trading_day(now) and not os.environ.get("FORCE_RUN"):
            reason = "주말" if now.weekday() >= 5 else "휴장일"
            logger.info(f"[main] {reason}({now:%Y-%m-%d}) — 실행 건너뜀")
            sys.exit(0)

        if not market_calendar.is_year_covered(now):
            # 휴장일 표가 없는 연도 — 달력 판정만으로는 음력 연휴를 놓칠 수 있다.
            # 아래 '거래일 기준 기록'(bar_date)이 2차 방어선이므로 실행은 계속한다.
            logger.warning(
                f"[main] ⚠ {now.year}년 휴장일 표 미등록(src/market_calendar.py 갱신 필요) "
                f"— 거래일은 수집 데이터의 bar_date 로 판단합니다."
            )

        date_str = now.strftime("%Y-%m-%d")

        spreadsheet_id = os.environ.get(SPREADSHEET_ID_ENV_KEY)
        if not spreadsheet_id:
            logger.warning(f"[main] 환경변수 {SPREADSHEET_ID_ENV_KEY} 가 설정되지 않았습니다.")
            sys.exit(1)

        try:
            stock_list = sheets.load_stock_list(spreadsheet_id)
        except Exception as e:
            logger.warning(f"[main] 종목 목록 로드 실패: {e}")
            notifier.send_report([], [{"code": "N/A", "name": "N/A", "close": None, "error": str(e)}], date_str)
            sys.exit(1)

        if not stock_list:
            logger.warning("[main] 종목 목록이 비어 있습니다.")
            notifier.send_report(
                [],
                [{"code": "N/A", "name": "N/A", "close": None, "error": "Dashboard 시트에 종목이 없습니다."}],
                date_str,
            )
            sys.exit(1)

        try:
            success_list, failed_list = pipeline.collect_snapshots(stock_list)
        except Exception as e:
            logger.warning(f"[main] 크롤링 실패: {e}")
            notifier.send_report([], [{"code": "N/A", "name": "N/A", "close": None, "error": str(e)}], date_str)
            sys.exit(1)

        # 시트 '날짜' 컬럼은 실행일이 아니라 **데이터가 실제로 속한 거래일**(bar_date)로
        # 기록한다. 달력에 없는 휴장일에 크론이 돌아 직전 거래일 종가를 받아와도 그 종가의
        # 원래 날짜로 들어가므로, sheets.write_stock_data 의 (날짜,종목코드) 중복 스킵이
        # 걸려 같은 값이 다른 날짜로 두 번 쌓이지 않는다. bar_date 부재 시에만 실행일로 폴백.
        stale = [s for s in success_list if s.get("bar_date") and s["bar_date"] != date_str]
        if stale:
            logger.warning(
                f"[main] ⚠ 최신 거래일이 오늘({date_str})이 아닌 종목 {len(stale)}건 "
                f"(기준일 예: {stale[0]['bar_date']}) — 해당 거래일로 기록합니다(중복은 자동 스킵)."
            )

        if success_list:
            try:
                rows = [[
                    s.get("bar_date") or date_str,
                    s["code"], s["name"],
                    s.get("open"), s.get("close"), s.get("low"), s.get("high"), s.get("volume"),
                    s.get("macd_1d"), s.get("rsi_1d"), s.get("macd_60m"), s.get("rsi_60m"),
                    s.get("short_view"), s.get("long_view"),
                    s.get("bb_upper"), s.get("bb_mid"), s.get("bb_lower"),
                    s.get("per"), s.get("pbr"), s.get("roe"),
                    s.get("revenue"), s.get("net_income"),
                ] for s in success_list]
                sheets.write_stock_data(spreadsheet_id, rows)
            except Exception as e:
                logger.warning(f"[main] 시트 쓰기 실패: {e}")
                failed_list.append({"code": "N/A", "name": "N/A", "close": None, "error": f"시트 쓰기 실패: {e}"})

        try:
            notifier.send_report(success_list, failed_list, date_str)
        except Exception as e:
            logger.warning(f"[main] 알림 전송 실패: {e}")

        if failed_list:
            sys.exit(1)
        else:
            sys.exit(0)

    except SystemExit:
        raise
    except Exception as e:
        logger.warning(f"[main] 예상치 못한 오류: {e}")
        try:
            notifier.send_report([], [{"code": "N/A", "name": "N/A", "close": None, "error": str(e)}], "unknown")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
