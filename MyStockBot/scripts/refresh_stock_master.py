"""KIS 종목마스터(KOSPI/KOSDAQ) 수동 1회 갱신 스크립트.

마스터 다운로드는 KIS 인증이 필요 없는 공개 정적 파일이라 .env(dotenv) 로드가 불필요하다.

사용법(MyStockBot 디렉터리에서):
    python scripts/refresh_stock_master.py
"""
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

import db
import stock_master


def main() -> None:
    db.init_db()
    count = stock_master.refresh_stock_master()
    print(f"[refresh_stock_master] 완료: {count}건")


if __name__ == "__main__":
    main()
