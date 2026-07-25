"""관심종목 단일 소스화 — SQLite(웹앱)와 Google Sheets Dashboard(크론)를 동기화.

## 왜 필요한가
관심종목 목록이 두 곳에 따로 있었다:
  · 웹앱   → SQLite `watchlist` (db.load_watchlist) — 화면·수집루프·모의투자가 사용
  · 크론   → Google Sheets `Dashboard` A열 (sheets.load_stock_list) — 일일 배치가 사용
GitHub Actions 러너는 매 실행마다 새로 클론되므로 서버의 SQLite 파일을 볼 수 없다.
따라서 두 저장소를 없앨 수는 없고, **양방향으로 수렴**시키는 것이 실질적인 단일 소스다.

## 동기화 규칙
  · 앱 → 시트 (즉시): 관심종목 추가 시 Dashboard 에 upsert, 삭제 시 C열에 '해제' 표시.
    행을 지우지 않으므로 사용자가 시트에 직접 넣은 내용이 파괴되지 않는다.
  · 시트 → 앱 (주기): Dashboard 에서 앱에 **아직 없는 코드만** 추가한다.
    시트에서 사라진 코드를 앱에서 지우는 자동 삭제는 하지 않는다 — 시트 오독·권한 오류
    한 번이 관심종목 전체를 날리는 위험이 훨씬 크기 때문이다(삭제는 앱에서 수행).

## 실패 정책
Google 자격증명이나 SPREADSHEET_ID 가 없으면 동기화는 **조용히 비활성**된다(개인용 배포에서
시트 없이 웹앱만 쓰는 구성을 막지 않기 위함). 미러링 실패는 로그만 남기고 API 응답에
영향을 주지 않는다 — 관심종목 추가/삭제 자체는 SQLite 기준으로 이미 성공한 상태다.
"""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SPREADSHEET_ID_ENV_KEY

import db
import sheets

logger = logging.getLogger(__name__)


def _spreadsheet_id() -> str | None:
    return os.environ.get(SPREADSHEET_ID_ENV_KEY) or None


def is_enabled() -> bool:
    """시트 동기화 가능 여부(자격증명 + SPREADSHEET_ID). 네트워크 호출 없음."""
    return bool(_spreadsheet_id()) and sheets.credentials_available()


def mirror_add(code: str, name: str) -> str | None:
    """앱 → 시트: 관심종목 추가를 Dashboard 에 반영. 결과 문자열, 비활성/실패 시 None."""
    spreadsheet_id = _spreadsheet_id()
    if not is_enabled():
        return None
    try:
        result = sheets.upsert_dashboard_item(spreadsheet_id, code, name)
        logger.info("[watchlist_sync] 시트 반영(추가) %s %s → %s", code, name, result)
        return result
    except Exception as e:
        # 미러링 실패가 API 응답을 깨뜨리지 않도록 여기서 격리한다(앱 목록은 이미 갱신됨).
        logger.warning("[watchlist_sync] 시트 반영(추가) 실패 %s: %s", code, e)
        return None


def mirror_remove(code: str) -> bool:
    """앱 → 시트: 관심종목 삭제를 Dashboard C열 '해제' 표시로 반영. 반영했으면 True."""
    spreadsheet_id = _spreadsheet_id()
    if not is_enabled():
        return False
    try:
        changed = sheets.deactivate_dashboard_item(spreadsheet_id, code)
        if changed:
            logger.info("[watchlist_sync] 시트 반영(해제) %s", code)
        else:
            logger.info("[watchlist_sync] 시트에 해제할 항목 없음(이미 해제/미등록): %s", code)
        return changed
    except Exception as e:
        logger.warning("[watchlist_sync] 시트 반영(해제) 실패 %s: %s", code, e)
        return False


def _resolve_name(code: str, sheet_name: str) -> str:
    """시트 B열 이름 → 종목마스터 이름 → 코드 순으로 표시명을 결정."""
    if sheet_name:
        return sheet_name
    try:
        matches = db.search_stocks(code, limit=1)
        if matches and matches[0]["code"] == code:
            return matches[0]["name"]
    except Exception as e:
        logger.warning("[watchlist_sync] 종목마스터 이름 조회 실패 %s: %s", code, e)
    return code


def import_from_sheet() -> dict:
    """시트 → 앱: Dashboard 에만 있는 종목을 SQLite watchlist 에 추가한다.

    반환 {"enabled", "sheet_items", "added", "skipped", "failed"}.
    앱에 이미 있는 코드(비활성 포함)는 건드리지 않는다 — 사용자가 앱에서 삭제한 종목을
    시트 임포트가 매번 되살리는 일을 막기 위함이다.
    """
    spreadsheet_id = _spreadsheet_id()
    if not is_enabled():
        return {"enabled": False, "sheet_items": 0, "added": 0, "skipped": 0, "failed": 0}

    try:
        entries = [e for e in sheets.load_dashboard_entries(spreadsheet_id) if not e["inactive"]]
    except Exception as e:
        logger.warning("[watchlist_sync] Dashboard 읽기 실패 — 임포트 건너뜀: %s", e)
        return {"enabled": True, "sheet_items": 0, "added": 0, "skipped": 0, "failed": 1}

    try:
        known = {item["code"] for item in db.load_watchlist(include_inactive=True)}
    except Exception as e:
        logger.warning("[watchlist_sync] watchlist 로드 실패 — 임포트 건너뜀: %s", e)
        return {"enabled": True, "sheet_items": len(entries), "added": 0, "skipped": 0, "failed": 1}

    added = skipped = failed = 0
    for entry in entries:
        code = entry["code"]
        if code in known:
            skipped += 1
            continue
        try:
            db.add_watchlist_item(code, _resolve_name(code, entry["name"]))
            known.add(code)
            added += 1
        except db.DuplicateError:
            skipped += 1
        except Exception as e:
            logger.warning("[watchlist_sync] 시트→앱 추가 실패 %s: %s", code, e)
            failed += 1

    if added or failed:
        logger.info(
            "[watchlist_sync] 시트→앱 임포트: 추가 %d건 / 기존 %d건 / 실패 %d건 (시트 %d건)",
            added, skipped, failed, len(entries),
        )
    return {
        "enabled": True,
        "sheet_items": len(entries),
        "added": added,
        "skipped": skipped,
        "failed": failed,
    }
