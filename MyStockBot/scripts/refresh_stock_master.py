"""KIS 종목마스터(KOSPI/KOSDAQ) 수동 1회 갱신 스크립트.

마스터 다운로드는 KIS 인증이 필요 없는 공개 정적 파일이라 .env(dotenv) 로드가 불필요하다.

사용법(MyStockBot 디렉터리에서):
    python scripts/refresh_stock_master.py
"""
import logging
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

import db
import stock_master

# 엔트리포인트가 로깅 설정을 책임진다(모듈들은 getLogger 만 사용) — stock_master 내부
# 진행 로그도 이 설정으로 함께 보인다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    db.init_db()
    count = stock_master.refresh_stock_master()
    logger.info("[refresh_stock_master] 완료: %d건", count)


if __name__ == "__main__":
    main()
