"""KIS 종목마스터(kospi_code.mst / kosdaq_code.mst) 다운로드·파싱.

오프셋·인코딩은 KIS 공식 예제를 그대로 이식했다(추측 금지 원칙):
  https://github.com/koreainvestment/open-trading-api
  stocks_info/kis_kospi_code_mst.py, stocks_info/kis_kosdaq_code_mst.py

핵심 파싱 규칙(공식 예제와 동일):
  - cp949 인코딩, 한 줄(row)에 한 종목.
  - row 끝 N바이트(KOSPI=228, KOSDAQ=222)가 고정폭 part2(시가총액·PER 등 지표들).
    이 N은 "고정폭 필드 합계 + 개행 1바이트"라서 텍스트 모드로 읽으면(개행이
    '\\n' 한 글자로 정규화됨) 그대로 슬라이싱해도 맞아떨어진다.
  - part1 = row[0 : len(row) - N]
      단축코드 = part1[0:9].rstrip()   (6자리 숫자, 종목코드)
      표준코드 = part1[9:21].rstrip()  (미사용)
      한글명   = part1[21:].strip()
  - market 은 어느 파일을 파싱했는지로 결정(part2 필드는 파싱하지 않음 — 이 앱은
    code/name/market 만 필요).

다운로드 서버(new.real.download.dws.co.kr)는 인증이 필요 없는 공개 정적 파일이지만,
공식 예제가 `ssl._create_unverified_context` 로 인증서 검증을 우회하는 것과 동일하게
여기서도 requests verify=False 를 쓴다(구식/자체서명 인증서 대응, 공식 예제 그대로 이식).
"""
import logging
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    KIS_MASTER_URLS,
    STOCK_MASTER_MIN_RATIO,
    STOCK_MASTER_MIN_ROWS_PER_MARKET,
    STOCK_MASTER_STALE_DAYS,
)

import db

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 시장별 zip 내부 마스터 파일명 (공식 예제 그대로)
_MST_FILENAMES = {
    "KOSPI": "kospi_code.mst",
    "KOSDAQ": "kosdaq_code.mst",
}

# 시장별 라인 꼬리(고정폭 part2) 바이트 수 — 공식 예제의 len(row) - N 그대로.
_TAIL_LENGTHS = {
    "KOSPI": 228,
    "KOSDAQ": 222,
}

_DOWNLOAD_TIMEOUT_SECONDS = 30
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2


def _download_with_retry(url: str, dest_path: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS, verify=False)
            resp.raise_for_status()
            dest_path.write_bytes(resp.content)
            return
        except requests.RequestException as e:
            last_error = e
            logger.warning(f"[stock_master] 다운로드 실패(시도 {attempt}/{_MAX_RETRIES}): {url} — {e}")
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError(f"마스터 파일 다운로드 실패: {url}") from last_error


def _parse_mst_file(mst_path: Path, market: str) -> list[dict]:
    tail_len = _TAIL_LENGTHS[market]
    items = []
    with open(mst_path, mode="r", encoding="cp949") as f:
        for row in f:
            if len(row) <= tail_len:
                continue
            part1 = row[: len(row) - tail_len]
            code = part1[0:9].rstrip()
            name = part1[21:].strip()
            if not code or not name:
                continue
            # 단축코드가 6자리 숫자가 아닌 특수건(공백 패딩 이상 등)은 제외.
            # ETF/ETN/우선주/SPAC 등은 코드가 정상 6자리 숫자이므로 포함된다.
            if len(code) == 6 and code.isdigit():
                items.append({"code": code, "name": name, "market": market})
    return items


def _download_and_parse_market(market: str, base_dir: Path) -> list[dict]:
    url = KIS_MASTER_URLS[market]
    zip_path = base_dir / f"{market.lower()}_code.zip"
    logger.info(f"[stock_master] {market} 마스터 다운로드 시작: {url}")
    _download_with_retry(url, zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(base_dir)

    mst_path = base_dir / _MST_FILENAMES[market]
    if not mst_path.exists():
        raise FileNotFoundError(f"압축 해제 후 마스터 파일을 찾을 수 없음: {mst_path}")

    items = _parse_mst_file(mst_path, market)
    logger.info(f"[stock_master] {market} 파싱 완료: {len(items)}건")
    return items


def download_and_parse() -> list[dict]:
    """KOSPI/KOSDAQ 종목마스터를 다운로드·파싱해 [{code, name, market}] 로 반환.

    실패 시 예외를 던진다 — 호출부(스케줄러/startup/스크립트)에서 각자 로깅·무시 처리.
    """
    all_items: list[dict] = []
    with TemporaryDirectory(prefix="mystockbot_master_") as tmp_dir:
        base_dir = Path(tmp_dir)
        for market in ("KOSPI", "KOSDAQ"):
            items = _download_and_parse_market(market, base_dir)
            all_items.extend(items)
    return all_items


def _delisting_guard_ok(rows: list[dict]) -> bool:
    """이번 파일로 "사라진 코드 = 상장폐지"를 판정해도 되는지.

    시장 하나가 통째로 실패하는 경우는 이미 안전하다 — _download_with_retry 가 예외를
    던져 upsert 자체가 실행되지 않는다. 진짜 위험은 **부분 성공**이다: zip 은 열리는데
    내용이 잘렸거나 인코딩이 어긋나 코드 필터에서 대량 탈락하면, rows 는 정상적으로
    돌아오고 나머지 전 종목이 상폐로 찍힌다.

    두 가지를 본다.
      ① 시장별 절대 하한 — KOSPI/KOSDAQ 각각 최소 건수를 넘는가
      ② 기존 대비 상대 하한 — 상장 중 종목 수가 갑자기 5% 넘게 줄지 않았는가
         (실제 상폐는 연간 수십 건 규모라 정상 갱신에서는 절대 안 걸린다)
    """
    by_market: dict[str, int] = {}
    for row in rows:
        by_market[row["market"]] = by_market.get(row["market"], 0) + 1

    for market in ("KOSPI", "KOSDAQ"):
        n = by_market.get(market, 0)
        if n < STOCK_MASTER_MIN_ROWS_PER_MARKET:
            logger.warning(
                "[stock_master] 상폐 판정 보류 — %s 가 %d건으로 하한(%d) 미만. "
                "파일이 잘렸을 수 있어 데이터만 갱신한다.",
                market, n, STOCK_MASTER_MIN_ROWS_PER_MARKET,
            )
            return False

    previous = db.count_stock_master()
    if previous and len(rows) < previous * STOCK_MASTER_MIN_RATIO:
        logger.warning(
            "[stock_master] 상폐 판정 보류 — 종목 수가 %d→%d 로 급감(기준 %.0f%%). "
            "파일 이상이 의심되어 데이터만 갱신한다.",
            previous, len(rows), STOCK_MASTER_MIN_RATIO * 100,
        )
        return False

    return True


def refresh_stock_master() -> int:
    """마스터를 다운로드해 DB에 upsert. 반영 건수 반환.

    무결성 가드를 통과하면 이번 파일에서 사라진 코드를 상장폐지로 표시한다 — 그래야
    상폐 종목이 검색·자동완성에서 사라진다. 가드가 막으면 upsert 만 하고 판정은 미룬다.
    """
    logger.info("[stock_master] 종목마스터 갱신 시작")
    rows = download_and_parse()
    mark_delisted = _delisting_guard_ok(rows)
    count = db.upsert_stock_master(rows, mark_missing_delisted=mark_delisted)
    logger.info(
        "[stock_master] 종목마스터 갱신 완료: %d건 (상폐 판정 %s)",
        count, "적용" if mark_delisted else "보류",
    )
    return count


def needs_refresh() -> bool:
    """stock_master 가 비어있거나 가장 오래된 updated_at 이 STALE_DAYS 초과면 True.

    db.py 의 updated_at 은 SQLite datetime('now')(UTC 기준 naive 문자열)로 저장되므로,
    비교 기준도 UTC 로 맞춘다. datetime.utcnow()는 3.12부터 deprecated 이므로
    datetime.now(timezone.utc)를 naive 로 변환해 사용한다.
    """
    meta = db.get_stock_master_meta()
    count = meta.get("count") or 0
    if count == 0:
        return True

    oldest = meta.get("oldest_updated_at")
    if not oldest:
        return True

    try:
        oldest_dt = datetime.strptime(oldest, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True

    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    return (now_utc_naive - oldest_dt) > timedelta(days=STOCK_MASTER_STALE_DAYS)


if __name__ == "__main__":
    refresh_stock_master()
