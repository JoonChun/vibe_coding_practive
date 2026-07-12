import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import crawler


def collect_snapshots(stock_list: list[dict]) -> tuple[list[dict], list[dict]]:
    """관심종목 리스트에 대해 크롤러를 실행해 (성공, 실패) 스냅샷 목록을 반환."""
    print(f"[pipeline] 스냅샷 수집 시작 ({len(stock_list)}종목)")
    return crawler.fetch_all(stock_list)
