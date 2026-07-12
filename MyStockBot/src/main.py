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
import pipeline
import sheets
import notifier


def main():
    try:
        tz = ZoneInfo(TIMEZONE)
        now = datetime.now(tz=tz)

        if now.weekday() >= 5 and not os.environ.get("FORCE_RUN"):
            print("[main] 주말 — 실행 건너뜀")
            sys.exit(0)

        date_str = now.strftime("%Y-%m-%d")

        spreadsheet_id = os.environ.get(SPREADSHEET_ID_ENV_KEY)
        if not spreadsheet_id:
            print(f"[main] 환경변수 {SPREADSHEET_ID_ENV_KEY} 가 설정되지 않았습니다.")
            sys.exit(1)

        try:
            stock_list = sheets.load_stock_list(spreadsheet_id)
        except Exception as e:
            print(f"[main] 종목 목록 로드 실패: {e}")
            notifier.send_report([], [{"code": "N/A", "name": "N/A", "close": None, "error": str(e)}], date_str)
            sys.exit(1)

        if not stock_list:
            print("[main] 종목 목록이 비어 있습니다.")
            notifier.send_report(
                [],
                [{"code": "N/A", "name": "N/A", "close": None, "error": "Dashboard 시트에 종목이 없습니다."}],
                date_str,
            )
            sys.exit(1)

        try:
            success_list, failed_list = pipeline.collect_snapshots(stock_list)
        except Exception as e:
            print(f"[main] 크롤링 실패: {e}")
            notifier.send_report([], [{"code": "N/A", "name": "N/A", "close": None, "error": str(e)}], date_str)
            sys.exit(1)

        if success_list:
            try:
                rows = [[
                    date_str,
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
                print(f"[main] 시트 쓰기 실패: {e}")
                failed_list.append({"code": "N/A", "name": "N/A", "close": None, "error": f"시트 쓰기 실패: {e}"})

        try:
            notifier.send_report(success_list, failed_list, date_str)
        except Exception as e:
            print(f"[main] 알림 전송 실패: {e}")

        if failed_list:
            sys.exit(1)
        else:
            sys.exit(0)

    except SystemExit:
        raise
    except Exception as e:
        print(f"[main] 예상치 못한 오류: {e}")
        try:
            notifier.send_report([], [{"code": "N/A", "name": "N/A", "close": None, "error": str(e)}], "unknown")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
