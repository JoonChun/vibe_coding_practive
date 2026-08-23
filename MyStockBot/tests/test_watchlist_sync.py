"""관심종목 단일 소스화 — 시트 Dashboard 파싱/동기화 규칙 테스트.

gspread 네트워크 호출은 하지 않는다. 파싱 순수함수(_parse_dashboard_rows)는 직접 검증하고,
동기화(import_from_sheet)는 시트 읽기만 monkeypatch 해 SQLite 반영 규칙을 검증한다.
"""
import sheets
import watchlist_sync


def test_parse_dashboard_rows_normalizes_and_filters():
    rows = [
        ["종목코드", "종목명", "상태"],
        ["5930", "삼성전자", ""],          # 앞자리 0 유실 → zfill 복원
        ["", "빈 코드", ""],               # 코드 없음 → 제외
        ["ABCDEFG", "형식 오류", ""],       # 7자 → 제외
        ["035720", "카카오", "해제"],       # 해제 표시
        ["000660", "SK하이닉스"],           # C열 자체가 없는 행
    ]
    parsed = sheets._parse_dashboard_rows(rows)

    assert [p["code"] for p in parsed] == ["005930", "035720", "000660"]
    assert parsed[0]["row_number"] == 2  # 헤더 다음 행부터
    assert parsed[1]["inactive"] is True
    assert parsed[2]["inactive"] is False


def test_inactive_mark_is_case_and_space_tolerant():
    assert sheets._is_inactive_mark("해제") is True
    assert sheets._is_inactive_mark("  해제 ") is True
    assert sheets._is_inactive_mark("") is False
    assert sheets._is_inactive_mark(None) is False
    assert sheets._is_inactive_mark("수집중") is False


def test_load_stock_list_excludes_inactive(monkeypatch):
    entries = [
        {"code": "005930", "name": "삼성전자", "inactive": False, "row_number": 2},
        {"code": "035720", "name": "카카오", "inactive": True, "row_number": 3},
    ]
    monkeypatch.setattr(sheets, "load_dashboard_entries", lambda _id: entries)

    result = sheets.load_stock_list("sheet-id")

    assert result == [{"code": "005930", "name": "삼성전자"}]


def test_import_from_sheet_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(watchlist_sync, "is_enabled", lambda: False)

    result = watchlist_sync.import_from_sheet()

    assert result == {
        "enabled": False, "sheet_items": 0, "added": 0, "skipped": 0, "failed": 0
    }


def test_import_from_sheet_adds_only_unknown_codes(monkeypatch, tmp_path):
    """앱에 이미 있는 코드(비활성 포함)는 건드리지 않는다 — 삭제한 종목이 되살아나면 안 됨."""
    import db

    monkeypatch.setenv("SPREADSHEET_ID", "sheet-id")
    monkeypatch.setattr(watchlist_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(
        watchlist_sync.sheets,
        "load_dashboard_entries",
        lambda _id: [
            {"code": "005930", "name": "삼성전자", "inactive": False, "row_number": 2},
            {"code": "035720", "name": "카카오", "inactive": False, "row_number": 3},
            {"code": "000660", "name": "SK하이닉스", "inactive": True, "row_number": 4},
        ],
    )

    # 005930 = 활성, 035720 = 사용자가 앱에서 삭제(비활성)
    added_calls = []
    monkeypatch.setattr(
        watchlist_sync.db,
        "load_watchlist",
        lambda include_inactive=False: [
            {"code": "005930", "name": "삼성전자"},
            {"code": "035720", "name": "카카오"},
        ],
    )
    monkeypatch.setattr(
        watchlist_sync.db,
        "add_watchlist_item",
        lambda code, name: added_calls.append((code, name)),
    )

    result = watchlist_sync.import_from_sheet()

    assert added_calls == []          # 되살리지 않음
    assert result["added"] == 0
    assert result["skipped"] == 2     # 해제(000660)는 애초에 대상 아님
    assert result["sheet_items"] == 2
    assert isinstance(db.DuplicateError, type)  # db 계약 유지 확인


def test_import_from_sheet_adds_new_code(monkeypatch):
    monkeypatch.setattr(watchlist_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(
        watchlist_sync.sheets,
        "load_dashboard_entries",
        lambda _id: [{"code": "000660", "name": "", "inactive": False, "row_number": 2}],
    )
    monkeypatch.setattr(
        watchlist_sync.db, "load_watchlist", lambda include_inactive=False: []
    )
    monkeypatch.setattr(
        watchlist_sync.db, "search_stocks", lambda q, limit=1: [
            {"code": "000660", "name": "SK하이닉스", "market": "KOSPI"}
        ]
    )
    added = []
    monkeypatch.setattr(
        watchlist_sync.db, "add_watchlist_item", lambda code, name: added.append((code, name))
    )

    result = watchlist_sync.import_from_sheet()

    # 시트 B열이 비어 있으면 종목마스터 이름으로 보강한다.
    assert added == [("000660", "SK하이닉스")]
    assert result["added"] == 1


def test_import_from_sheet_survives_sheet_read_failure(monkeypatch):
    monkeypatch.setattr(watchlist_sync, "is_enabled", lambda: True)

    def _boom(_id):
        raise RuntimeError("gspread 403")

    monkeypatch.setattr(watchlist_sync.sheets, "load_dashboard_entries", _boom)

    result = watchlist_sync.import_from_sheet()

    assert result["enabled"] is True
    assert result["added"] == 0
    assert result["failed"] == 1


def test_mirror_add_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(watchlist_sync, "is_enabled", lambda: False)
    assert watchlist_sync.mirror_add("005930", "삼성전자") is None


def test_mirror_remove_swallows_sheet_error(monkeypatch):
    """미러링 실패가 API 응답(이미 성공한 삭제)을 깨뜨리면 안 된다."""
    monkeypatch.setenv("SPREADSHEET_ID", "sheet-id")
    monkeypatch.setattr(watchlist_sync, "is_enabled", lambda: True)

    def _boom(_id, _code):
        raise RuntimeError("gspread quota")

    monkeypatch.setattr(watchlist_sync.sheets, "deactivate_dashboard_item", _boom)

    assert watchlist_sync.mirror_remove("005930") is False
