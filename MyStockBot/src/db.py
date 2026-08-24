import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH

# db 에 저장되는 fetched_at 등 UTC naive 타임스탬프 포맷 — SQLite datetime('now')와 동일 형식.
_UTC_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


class DuplicateError(Exception):
    """이미 활성 상태인 관심종목을 다시 추가하려 할 때 발생."""


def get_connection() -> sqlite3.Connection:
    data_dir = os.path.dirname(DB_PATH)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _migrate_decision_alert_state(conn: sqlite3.Connection) -> None:
    """구버전 스키마(fund_present 0/1)를 fund_mask 비트마스크로 교체한다.

    두 컬럼의 **의미가 달라서** 값을 그대로 옮길 수 없다(0/1 vs 0~7 비트마스크).
    이 테이블은 "무엇을 마지막으로 알렸는지"만 담은 캐시이므로 버려도 손실은
    키당 무음 시딩 1회뿐이다 — 값을 억지로 변환해 잘못된 기준선을 남기는 것보다 낫다.

    `CREATE TABLE IF NOT EXISTS` 는 기존 테이블에 컬럼을 추가하지 않으므로 이 단계가 필요하다.
    조건부이므로 부팅마다 지우지 않는다.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'decision_alert_state'"
    ).fetchone()
    if exists is None:
        return
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(decision_alert_state)")}
    if "fund_mask" not in columns:
        conn.execute("DROP TABLE decision_alert_state")


def _migrate_paper_trades(conn: sqlite3.Connection) -> None:
    """paper_trades 에 price_source·market_status·realized_pnl 컬럼을 더한다.

    `CREATE TABLE IF NOT EXISTS` 는 기존 테이블에 컬럼을 추가하지 않으므로 이 단계가
    필요하다. **decision_alert_state 처럼 DROP 하지 않는다** — 이건 캐시가 아니라
    사용자의 거래 기록이고, 버리면 되살릴 방법이 없다. ALTER TABLE ADD COLUMN 으로
    더하고, 기존 행은 세 값이 NULL 로 남는다("기록되기 전의 거래" = 알 수 없음).
    NULL 을 'market'/'open' 으로 채워 넣지 않는다 — 모르는 것을 안다고 적는 셈이다.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(paper_trades)")}
    if not existing:  # 테이블이 아직 없다(방금 CREATE 된다) → 할 일 없음
        return
    for column, ddl in (
        ("price_source", "ALTER TABLE paper_trades ADD COLUMN price_source TEXT"),
        ("market_status", "ALTER TABLE paper_trades ADD COLUMN market_status TEXT"),
        ("realized_pnl", "ALTER TABLE paper_trades ADD COLUMN realized_pnl REAL"),
    ):
        if column not in existing:
            conn.execute(ddl)


def _migrate_stock_master(conn: sqlite3.Connection) -> None:
    """stock_master 에 delisted 컬럼을 더한다.

    paper_trades 관례를 따라 ALTER 로 더한다 — 이 테이블은 종목명·시장의 유일한
    출처이고(관심종목 목록이 LEFT JOIN 으로 market 을 얹는다) 버리면 다음 마스터
    갱신까지 이름이 비므로, DROP 계열이 아니다.
    기존 행은 DEFAULT 0(상장 중)으로 시작한다 — 다음 갱신에서 실제로 사라진 코드만
    1 로 바뀐다. 모르는 것을 '상폐'로 단정하지 않는 방향이다.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(stock_master)")}
    if not existing:  # 테이블이 아직 없다(방금 CREATE 된다) → 할 일 없음
        return
    if "delisted" not in existing:
        conn.execute(
            "ALTER TABLE stock_master ADD COLUMN delisted INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_candles_source(conn: sqlite3.Connection) -> None:
    """candles 에 source 컬럼을 더한다 — 그 봉을 **어느 규약으로** 받았는지 기록한다.

    왜 필요한가: KIS(원주가 정수)와 yfinance(auto_adjust=True — 분할·배당 조정)는
    조정 규약이 다른데, 지금까지 같은 (code, tf, t) PK 에 번갈아 REPLACE 되어 한
    종목 안에서 기준가가 섞일 수 있었다. rule_eval 은 이 문제를 알고 **읽는 쪽에서**
    yfinance 폴백을 포기하는 방식으로 회피해 왔다 — 이 컬럼은 그 회피를 쓰는 쪽이
    아니라 저장하는 쪽에서 끝내기 위한 것이다.

    paper_trades 관례를 따라 ALTER 로 더하고 **기존 행은 NULL 로 둔다.** 'kis' 로
    일괄 채우지 않는다 — 실제로 그 행들 중 일부는 yfinance·시트 백필 산이고,
    모르는 것을 안다고 적으면 나중에 구분할 방법이 사라진다. NULL 은 "규약 불명"이며,
    다음 수집이 그 (code, tf) 를 새 소스로 덮어쓸 때 자연히 정리된다.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(candles)")}
    if not existing:  # 테이블이 아직 없다(방금 CREATE 된다) → 할 일 없음
        return
    if "source" not in existing:
        conn.execute("ALTER TABLE candles ADD COLUMN source TEXT")


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_master (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                market TEXT NOT NULL,
                updated_at TEXT,
                -- 마스터 파일에서 사라진 종목(상장폐지 추정). 행을 지우지 않는 이유는
                -- 보유 중인 상폐 종목의 이름·시장이 필요하고 재상장 시 되살려야 하기 때문.
                delisted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        _migrate_stock_master(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stock_master_name ON stock_master(name)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                code TEXT NOT NULL,
                tf TEXT NOT NULL,
                t INTEGER NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (code, tf, t)
            )
            """
        )
        # 120m/240m 오염 행 정리 — 예전 리샘플이 positional(조회창 시작 기준)이라 같은
        # 실제 구간이 재조회 시각마다 다른 t 로 저장돼 겹치는 봉이 쌓였다. 지금은
        # clock-aligned(t 가 버킷 크기로 나누어떨어짐)로만 저장하므로, 경계에 안 맞는
        # 행 = 옛 방식의 잔재다. 조건 자체가 멱등이라 부팅마다 실행해도 안전하다.
        conn.execute("DELETE FROM candles WHERE tf = '120m' AND t % 7200 != 0")
        conn.execute("DELETE FROM candles WHERE tf = '240m' AND t % 14400 != 0")
        _migrate_candles_source(conn)

        # ── 캔들 원천 고갈 바닥 ──
        # "이 종목·tf 는 원천에 더 이상 과거가 없다"는 확인 결과. 인메모리로만 두면
        # 재시작마다 잊혀서, 이미 고갈을 확인한 종목도 첫 차트 로딩에서 최대 15페이지
        # 페이지네이션(콜당 0.5초 스로틀)을 다시 시도한다 — market_holidays 를 영속화한
        # 것과 같은 이유다.
        #
        # source 를 함께 남기는 이유: KIS 토큰이 죽어 yfinance 폴백(일봉 2년)으로 채운
        # 결과를 바닥으로 굳히면, 그 종목 일봉이 2년에서 영구히 잘린다. 바닥은 'kis'
        # 확인분만 신뢰한다(아래 set_candle_history_floor 참조).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candle_history_floor (
                code TEXT NOT NULL,
                tf TEXT NOT NULL,
                floor_t INTEGER NOT NULL,
                source TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (code, tf)
            )
            """
        )
        # ── KRX 휴장일 캐시 ──
        # KIS 국내휴장일조회(CTCA0903R)는 "가급적 1일 1회 호출"을 요청하므로 결과를 여기
        # 영속 저장한다. in-memory 캐시만 쓰면 서버 재시작마다 재호출하게 된다.
        # is_open = opnd_yn(개장일여부) 을 0/1 로 저장.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS market_holidays (
                date TEXT PRIMARY KEY,
                is_open INTEGER NOT NULL,
                fetched_at TEXT NOT NULL
            )
            """
        )

        # ── 판정 전환 알림 기준선 ──
        # "직전 사이클과 비교"가 아니라 "마지막으로 **알린** 판정과 비교"한다.
        # in-memory 로만 들고 있으면 (1) 서버 재시작 때 기준선이 사라져 재부팅마다 전 종목
        # 알림이 터지고, (2) 판정이 A↔B 로 왕복할 때 매번 알림이 나간다. 영속화하면 둘 다
        # 공짜로 해결된다 — 왕복해서 돌아온 판정은 마지막 알린 값과 같으므로 알리지 않는다.
        #
        # fund_mask / source 도 함께 저장한다: 재무데이터가 뒤늦게 도착하거나(장기 판정이
        # 재무 ±3점만큼 통째로 이동) 데이터 출처가 kis↔yfinance 로 바뀌면 판정이 바뀌는데,
        # 그건 시장이 아니라 **입력 구성**이 바뀐 것이라 알릴 사건이 아니다.
        #
        # fund_mask 는 per/pbr/roe 의 **존재 여부 비트마스크**(0~7)다. 예전엔 any() 로 접은
        # 0/1 이었는데, 세 값은 각각 독립적으로 ±1 점을 내고 관망 구간이 score==0 단일 점이라
        # **한 필드만 도착·소실해도** 측이 바뀐다. 1비트로는 그 사이클을 구분할 수 없어
        # "재무 도착이 매매 신호로 보이는" 경로가 그대로 열려 있었다(적자·미공시 종목은
        # per 만 결측인 경우가 흔하다).
        # 재무 '점수'를 저장하는 대안은 채택하지 않았다 — KIS 의 PER/PBR 은 현재가로
        # 계산되므로 주가가 움직이면 점수도 움직인다. 점수를 입력 지문으로 쓰면 진짜 시장
        # 전환까지 무음 흡수해 오알림을 알림 누락으로 바꾸는 것뿐이다.
        #
        # notified_at 은 실제 발송 시각(쿨다운 기준), updated_at 은 행을 마지막으로 만진
        # 시각(TTL 재시딩 기준)이다. 무음 시딩은 notified_at 을 건드리지 않는다.
        _migrate_decision_alert_state(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_alert_state (
                code TEXT NOT NULL,
                view_kind TEXT NOT NULL,
                view TEXT NOT NULL,
                fund_mask INTEGER NOT NULL DEFAULT 0,
                source TEXT,
                notified_at TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (code, view_kind)
            )
            """
        )
        # 고아 기준선 정리 — 관심종목에서 빠진 코드의 행을 남겨두면 나중에 다시 추가했을 때
        # 그동안의 시장 움직임이 '방금 전환'으로 알려지고, /api/alerts/config 의 baselines
        # 카운트도 실제보다 커진다. 부팅 때 한 번 쓸어낸다(활성 목록이 진실의 원천).
        conn.execute(
            "DELETE FROM decision_alert_state WHERE code NOT IN "
            "(SELECT code FROM watchlist WHERE is_active = 1)"
        )

        # ── 모의투자(Paper Trading) ── 개인용 단일 계좌(id=1 싱글턴)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL NOT NULL,
                seed REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_holdings (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                qty INTEGER NOT NULL,
                avg_cost REAL NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL DEFAULT (datetime('now')),
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                qty INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                -- 체결가가 어디서 왔는지. 'market' = 수집된 시세, 'book' = 장부가(평균단가)
                -- 대체 체결. 이걸 남기지 않으면 시세가 없어 평균단가로 청산한 매도가 실제
                -- 시장가 체결과 구별되지 않는다 — 즉 "그 가격에 팔렸다"가 사실이 아닌
                -- 기록이 남는다. 성적 해석의 근거가 되는 값이라 반드시 구분해 둔다.
                price_source TEXT,
                -- 체결 시점의 장 상태('open'/'pre'/'closed'/'holiday'). 장외 체결은
                -- 현실에서 불가능하므로, 성적을 볼 때 걸러낼 수 있어야 한다.
                market_status TEXT,
                -- 매도에서 확정된 실현손익 = (체결가 - 그 시점 평균단가) * 수량. 매수는 NULL.
                -- 평균단가는 체결 트랜잭션 안에서만 정확히 알 수 있으므로 여기서 함께 남긴다
                -- (나중에 거래내역만 보고 되계산하려면 평균단가 이력이 필요해 불가능하다).
                realized_pnl REAL
            )
            """
        )
        _migrate_paper_trades(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_paper_trades_ts ON paper_trades(ts DESC)"
        )

        # ── 알림 이력 ── "실제로 알림으로 나간 판정 전환"의 기록.
        #
        # decision_alert_state 와 역할이 다르다: 그쪽은 종목·종류당 **한 행**(마지막으로
        # 알린 판정)만 들고 게이트 판단에 쓰이는 캐시다. 이쪽은 append-only 기록이라
        # "언제 어떻게 바뀌었나"에 답한다 — 알림을 놓쳤거나 지난 며칠을 되짚을 때 필요하다.
        #
        # 쿨다운·히스테리시스로 눌린 전환은 넣지 않는다. 그것들은 _pending 에 남아 조건이
        # 풀리면 발화하므로 유실이 아니라 지연이고, 넣으면 같은 전환이 두 번 보인다.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS decision_alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notified_at TEXT NOT NULL DEFAULT (datetime('now')),
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                view_kind TEXT NOT NULL,
                before_view TEXT NOT NULL,
                after_view TEXT NOT NULL,
                close REAL,
                change_pct REAL,
                -- 실제로 **성공한** 채널만 콤마로 잇는다. 실패한 채널을 실으면
                -- "어디로 갔는지"가 사실과 달라진다.
                channels TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alert_history_id "
            "ON decision_alert_history(id DESC)"
        )
        conn.commit()
    finally:
        conn.close()


def load_watchlist(include_inactive: bool = False) -> list[dict]:
    # stock_master 를 LEFT JOIN 해 market('KOSPI'|'KOSDAQ')을 함께 반환한다.
    # 마스터에 아직 없는 코드(갱신 전·상장폐지 등)는 market = NULL.
    conn = get_connection()
    try:
        base_select = (
            "SELECT w.id, w.code, w.name, w.is_active, w.created_at, sm.market AS market "
            "FROM watchlist w LEFT JOIN stock_master sm ON sm.code = w.code "
        )
        if include_inactive:
            rows = conn.execute(base_select + "ORDER BY w.id").fetchall()
        else:
            rows = conn.execute(
                base_select + "WHERE w.is_active = 1 ORDER BY w.id"
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _normalize_code(code) -> str:
    raw = str(code).strip()
    if not raw:
        raise ValueError(f"잘못된 종목코드 형식: {code}")
    normalized = raw.zfill(6).upper()
    if len(normalized) != 6 or not normalized.isdigit():
        raise ValueError(f"잘못된 종목코드 형식: {code}")
    return normalized


def normalize_code(code) -> str:
    """종목코드 정규화(6자리 zero-padded 숫자)의 공개 인터페이스. 형식이 틀리면 ValueError."""
    return _normalize_code(code)


def add_watchlist_item(code, name) -> dict:
    normalized_code = _normalize_code(code)

    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, code, name, is_active, created_at FROM watchlist WHERE code = ?",
            (normalized_code,),
        ).fetchone()

        if existing is not None:
            if existing["is_active"]:
                raise DuplicateError(f"이미 등록된 종목입니다: {normalized_code}")
            conn.execute(
                "UPDATE watchlist SET is_active = 1, name = ? WHERE code = ?",
                (name, normalized_code),
            )
            # 알림 기준선을 여기서도 지운다 — **추가 시점이 경합 없는 지점이다.**
            # 삭제 시점에만 지우면, 그때 진행 중이던 수집 사이클이 사이클 끝에 기준선을
            # 되살릴 수 있다(watchlist 는 soft delete 라 행이 재사용된다). 추가 시점에
            # 한 번 더 지우면 재추가 직후의 기준선은 반드시 비어 있고, 첫 사이클이 조용히
            # 시딩하므로 "그동안의 시장 움직임"이 방금 전환으로 알려지지 않는다.
            conn.execute(
                "DELETE FROM decision_alert_state WHERE code = ?", (normalized_code,)
            )
            conn.commit()
            row = conn.execute(
                "SELECT id, code, name, is_active, created_at FROM watchlist WHERE code = ?",
                (normalized_code,),
            ).fetchone()
            return dict(row)

        conn.execute(
            "INSERT INTO watchlist (code, name) VALUES (?, ?)",
            (normalized_code, name),
        )
        # 신규 코드라도 고아 기준선이 남아 있을 수 있다(부활한 행·수동 조작).
        conn.execute(
            "DELETE FROM decision_alert_state WHERE code = ?", (normalized_code,)
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, code, name, is_active, created_at FROM watchlist WHERE code = ?",
            (normalized_code,),
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def remove_watchlist_item(code) -> bool:
    normalized_code = _normalize_code(code)

    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE watchlist SET is_active = 0 WHERE code = ? AND is_active = 1",
            (normalized_code,),
        )
        # 알림 기준선도 같은 트랜잭션에서 지운다. 남겨두면 나중에 이 종목을 다시 추가했을 때
        # 그동안 시장이 움직인 결과가 '방금 전환'으로 알려진다(watchlist 는 soft delete 라
        # 행이 재사용되므로 기준선이 저절로 사라지지 않는다).
        conn.execute(
            "DELETE FROM decision_alert_state WHERE code = ?", (normalized_code,)
        )
        # 캔들도 함께 정리한다 — 관심종목에서 빠지면 이 종목의 봉을 갱신할 주체가
        # 없어져 낡은 채로 남는다(실측으로 고아 캔들 1,878행이 쌓여 있었고, 매일
        # 백업 14벌에 그대로 따라다닌다). 다시 추가하면 백필이 즉시 재수집하므로
        # 되돌릴 수 있다. 바닥 기록도 같이 지운다(캔들이 없으면 거짓이 된다).
        conn.execute("DELETE FROM candles WHERE code = ?", (normalized_code,))
        conn.execute("DELETE FROM candle_history_floor WHERE code = ?", (normalized_code,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def upsert_stock_master(rows: list[dict], mark_missing_delisted: bool = False) -> int:
    """[{code, name, market}, ...] 를 stock_master 에 upsert.

    executemany 한 번 + commit 한 번 = 트랜잭션 1개. 반영 건수 반환.

    mark_missing_delisted=True 면 **이번 파일에 없던 코드**를 상장폐지로 표시한다
    (행은 지우지 않는다 — 보유 중인 상폐 종목의 이름·시장 정보가 필요하고, 재상장
    되면 되살려야 한다). 이번 파일에 들어온 코드는 항상 delisted=0 으로 되돌아가므로
    오탐이 나도 다음 정상 갱신에서 자동 복구된다.

    ★ 이 플래그는 **호출부가 파일 무결성을 검증한 뒤에만** 켜야 한다. 마스터 파일이
    잘린 채 정상 zip 으로 도착하면 행 수만 줄어든 채 조용히 성공하는데, 그때 켜면
    멀쩡한 전 종목이 상폐로 찍힌다(stock_master.refresh_stock_master 의 가드 참조).

    updated_at 은 파이썬에서 만든 단일 run_ts 로 바인딩한다 — SQLite datetime('now')
    는 행마다 재평가돼 초 경계를 넘으면 같은 실행분끼리 값이 갈리고, 그러면 "이번
    실행에 안 들어온 행" 판별이 어긋난다.
    """
    if not rows:
        return 0

    run_ts = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        if mark_missing_delisted:
            # 전부 상폐 후보로 표시해 두고, 아래 upsert 가 이번 파일에 있는 코드만
            # 0 으로 되돌린다 — 결과적으로 "파일에 없던 코드"만 1 로 남는다.
            #
            # updated_at 비교로 판별하지 않는 이유: 타임스탬프가 초 단위라 같은 초에
            # 두 번 갱신하면 "이번 실행분"과 "직전 실행분"이 구분되지 않아 아무도
            # 상폐로 잡히지 않는다(테스트로 확인). 이 방식은 시계 해상도와 무관하고,
            # 같은 트랜잭션 안이라 중간 상태가 밖에서 보이지도 않는다.
            conn.execute("UPDATE stock_master SET delisted = 1")

        conn.executemany(
            """
            INSERT INTO stock_master (code, name, market, updated_at, delisted)
            VALUES (?, ?, ?, ?, 0)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                market = excluded.market,
                updated_at = excluded.updated_at,
                delisted = 0
            """,
            [(row["code"], row["name"], row["market"], run_ts) for row in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def count_stock_master(market: str | None = None) -> int:
    """상장 중(delisted=0)인 종목 수. 마스터 파일 무결성 가드의 비교 기준."""
    conn = get_connection()
    try:
        if market is None:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM stock_master WHERE delisted = 0"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM stock_master WHERE delisted = 0 AND market = ?",
                (market,),
            ).fetchone()
        return int(row["n"]) if row else 0
    finally:
        conn.close()


def get_stock_master_meta() -> dict:
    """stock_master 건수와 가장 오래된 updated_at. **상장 중(delisted=0)만 센다.**

    startup/스케줄러에서 갱신 필요 여부(비어있음·7일 초과)를 판단하는 데 쓰인다.
    상폐 행을 포함하면 그 행의 updated_at 이 갱신되지 않아 MIN 이 영원히 옛날 값으로
    남고, needs_refresh() 가 매번 참이 되어 부팅마다 마스터를 다시 받게 된다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count, MIN(updated_at) AS oldest_updated_at "
            "FROM stock_master WHERE delisted = 0"
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


def search_stocks(q: str, limit: int = 10) -> list[dict]:
    """종목마스터에서 코드/종목명으로 검색.

    매칭: 코드 정확일치, 코드 prefix, 이름 부분일치(이름 prefix 포함).
    정렬: 코드 정확일치 > 코드 prefix > 이름 prefix > 이름 contains.
    q 가 없거나 공백뿐이면 빈 리스트. limit 은 1~30 사이로 강제.
    마스터 테이블이 비어 있어도 예외 없이 빈 리스트를 반환한다.
    """
    query = (q or "").strip()
    if not query:
        return []

    safe_limit = max(1, min(int(limit), 30))

    # LIKE 와일드카드(%, _)를 이스케이프해 검색어 원문 그대로 매칭한다.
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    prefix_pattern = f"{escaped}%"
    contains_pattern = f"%{escaped}%"

    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT code, name, market
            FROM stock_master
            WHERE delisted = 0
              AND (code = :q
               OR code LIKE :prefix ESCAPE '\\'
               OR name LIKE :contains ESCAPE '\\')
            ORDER BY
                CASE
                    WHEN code = :q THEN 0
                    WHEN code LIKE :prefix ESCAPE '\\' THEN 1
                    WHEN name LIKE :prefix ESCAPE '\\' THEN 2
                    ELSE 3
                END,
                code
            LIMIT :limit
            """,
            {
                "q": query,
                "prefix": prefix_pattern,
                "contains": contains_pattern,
                "limit": safe_limit,
            },
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_candles_source(code: str, tf: str) -> str | None:
    """(code, tf) 저장소에 기록된 조정 규약(source). 행이 없거나 규약 불명이면 None.

    같은 (code, tf) 안에 여러 소스가 섞여 있으면(마이그레이션 이전 데이터) 가장 최근
    행의 값을 대표로 본다 — 호출부는 이 값이 새 소스와 다르면 혼합으로 판단한다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT source FROM candles WHERE code = ? AND tf = ? AND source IS NOT NULL "
            "ORDER BY t DESC LIMIT 1",
            (code, tf),
        ).fetchone()
        return None if row is None else row["source"]
    finally:
        conn.close()


def delete_candles(code: str, tf: str | None = None) -> int:
    """(code[, tf]) 캔들 삭제. 삭제된 행 수 반환.

    캔들은 소스에서 재구축 가능한 캐시다 — 규약이 섞였거나 분할로 과거가 어긋났을 때
    잘못된 가격을 남겨두는 것보다 지우고 다시 받는 편이 낫다(오염된 리샘플 행을 부팅
    시 지우는 기존 정리와 같은 사상).
    """
    conn = get_connection()
    try:
        if tf is None:
            cur = conn.execute("DELETE FROM candles WHERE code = ?", (code,))
        else:
            cur = conn.execute("DELETE FROM candles WHERE code = ? AND tf = ?", (code, tf))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def upsert_candles(code: str, tf: str, items: list[dict], source: str | None = None) -> int:
    """캔들 영속 저장소에 upsert. items 는 [{t, open, high, low, close, volume}, ...].

    단일 트랜잭션(executemany + commit 1회). (code, tf, t) PK 충돌 시 덮어쓴다
    (KIS/yfinance 재수집 시 동일 캔들이 갱신될 수 있으므로 REPLACE가 맞다).
    빈 items 는 no-op(0 반환) — 실패한 fetch 결과로 기존 데이터를 지우지 않기 위함.

    source 는 그 봉을 받은 조정 규약("kis"|"yfinance"|"sheets"). 기본 None 은 "규약
    불명"이며 기존 호출부를 그대로 두기 위한 값이다 — 새 코드는 반드시 명시할 것.
    규약이 다른 소스로 덮어쓰는 것을 막는 책임은 호출부에 있다(candles 서비스 참조).
    """
    if not items:
        return 0

    fetched_at = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT OR REPLACE INTO candles
                (code, tf, t, open, high, low, close, volume, fetched_at, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    code, tf, item.get("t"),
                    item.get("open"), item.get("high"), item.get("low"),
                    item.get("close"), item.get("volume"),
                    fetched_at, source,
                )
                for item in items
            ],
        )
        conn.commit()
        return len(items)
    finally:
        conn.close()


def get_candles_store(code: str, tf: str, limit: int) -> list[dict]:
    """(code, tf) 저장소에서 t 오름차순 마지막 limit개 반환. 데이터 없으면 빈 리스트."""
    safe_limit = max(1, int(limit))

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT t, open, high, low, close, volume FROM candles "
            "WHERE code = ? AND tf = ? ORDER BY t DESC LIMIT ?",
            (code, tf, safe_limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def get_candles_store_before(code: str, tf: str, limit: int, before_t: int) -> list[dict]:
    """(code, tf) 저장소에서 t < before_t 인 캔들을 t 오름차순 마지막 limit개 반환.

    차트 왼쪽 스크롤(과거 페이지 로딩)용 커서 조회 — before_t 는 배타적 상한이다
    (프론트가 이미 가진 가장 오래된 봉의 t 를 그대로 넘기면 그보다 과거만 온다).
    데이터 없으면 빈 리스트.
    """
    safe_limit = max(1, int(limit))

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT t, open, high, low, close, volume FROM candles "
            "WHERE code = ? AND tf = ? AND t < ? ORDER BY t DESC LIMIT ?",
            (code, tf, int(before_t), safe_limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]
    finally:
        conn.close()


def create_backup(backup_dir: str | None = None, retention: int = 14) -> str | None:
    """운영 DB 스냅샷 백업. 생성한 백업 파일 경로를 반환한다(원본 없으면 None).

    sqlite3 의 backup API 를 쓴다 — WAL 모드에서 쓰기가 진행 중이어도 일관된
    스냅샷이 보장된다(파일 복사 cp 는 WAL 저널과 어긋난 조각을 뜰 수 있다).
    파일명은 mystockbot-YYYYMMDD.db (하루 1개 — 같은 날 재실행은 덮어쓴다).
    retention 개를 넘는 오래된 백업은 삭제한다. 기본 위치는 DB 옆 backups/
    (data/ 하위 — gitignore 대상이며 호스트 바인드 마운트라 컨테이너 밖에서 보인다).
    """
    if not os.path.exists(DB_PATH):
        return None

    directory = backup_dir or os.path.join(os.path.dirname(DB_PATH) or ".", "backups")
    os.makedirs(directory, exist_ok=True)
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
    dest_path = os.path.join(directory, f"mystockbot-{stamp}.db")

    src = get_connection()
    try:
        dst = sqlite3.connect(dest_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    backups = sorted(
        f for f in os.listdir(directory)
        if f.startswith("mystockbot-") and f.endswith(".db")
    )
    for old in backups[:-max(1, int(retention))]:
        try:
            os.remove(os.path.join(directory, old))
        except OSError:
            pass  # 지우기 실패가 백업 자체를 실패로 만들 이유는 없다

    return dest_path


def get_candle_history_floor(code: str, tf: str, max_age_days: int = 30) -> int | None:
    """(code, tf) 원천 고갈 바닥 epoch. 없거나 너무 오래된 기록이면 None.

    max_age_days 재검증: 바닥은 "더 과거가 없다"는 **부정 확인**이라 한번 굳으면 스스로
    풀리지 않는다(바닥이 딥 수집을 막고, 딥 수집이 없으면 바닥을 내릴 관측도 없다).
    실제 상장 이력은 늘어나지 않지만 원천 쪽 사정으로 잘못 굳었을 수 있으므로, 한 달에
    한 번은 무시하고 재확인하게 둔다 — 종목당 월 1회 페이지네이션은 사실상 공짜다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT floor_t FROM candle_history_floor "
            "WHERE code = ? AND tf = ? AND updated_at >= ?",
            (
                code, tf,
                (datetime.now(timezone.utc) - timedelta(days=max_age_days)).strftime(_UTC_TS_FORMAT),
            ),
        ).fetchone()
        return None if row is None else int(row["floor_t"])
    finally:
        conn.close()


def set_candle_history_floor(code: str, tf: str, floor_t: int, source: str) -> None:
    """원천 고갈 바닥 기록. **아래로만 내려간다** — 더 과거가 확인되면 갱신하고,
    위로는 되돌리지 않는다(그래야 한 번 확인한 깊이를 잃지 않는다).

    조건부 갱신을 SQL 한 문장에 담아 read-modify-write 경합을 없앤다.
    updated_at 은 값이 그대로여도 갱신한다 — 재검증 TTL 의 기준이기 때문이다.
    """
    now = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO candle_history_floor (code, tf, floor_t, source, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(code, tf) DO UPDATE SET
                floor_t = MIN(candle_history_floor.floor_t, excluded.floor_t),
                source = excluded.source,
                updated_at = excluded.updated_at
            """,
            (code, tf, int(floor_t), source, now),
        )
        conn.commit()
    finally:
        conn.close()


def clear_candle_history_floor(code: str, tf: str | None = None) -> None:
    """바닥 기록 삭제 — 캔들을 퍼지할 때 함께 부른다(퍼지 후에는 바닥이 거짓이 된다)."""
    conn = get_connection()
    try:
        if tf is None:
            conn.execute("DELETE FROM candle_history_floor WHERE code = ?", (code,))
        else:
            conn.execute(
                "DELETE FROM candle_history_floor WHERE code = ? AND tf = ?", (code, tf)
            )
        conn.commit()
    finally:
        conn.close()


def get_candles_age_seconds(code: str, tf: str) -> float | None:
    """(code, tf) 저장소의 max(fetched_at) 로부터 현재(UTC)까지 경과 초. 데이터 없으면 None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MAX(fetched_at) AS fetched_at FROM candles WHERE code = ? AND tf = ?",
            (code, tf),
        ).fetchone()
        fetched_at = row["fetched_at"] if row else None
        if not fetched_at:
            return None
        try:
            fetched_dt = datetime.strptime(fetched_at, _UTC_TS_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        return (datetime.now(timezone.utc) - fetched_dt).total_seconds()
    finally:
        conn.close()


# ────────────────────────────────────────────
# KRX 휴장일 캐시 (KIS CTCA0903R 결과 영속화)
# ────────────────────────────────────────────

def upsert_market_holidays(rows: list[dict]) -> int:
    """[{date: 'YYYY-MM-DD', is_open: bool}, ...] 를 upsert. 단일 트랜잭션. 반영 건수 반환.

    빈 리스트는 no-op(0) — 실패한 조회 결과로 기존 캐시를 지우지 않기 위함이다.
    """
    if not rows:
        return 0

    fetched_at = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO market_holidays (date, is_open, fetched_at) VALUES (?, ?, ?)",
            [(r["date"], 1 if r["is_open"] else 0, fetched_at) for r in rows],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_market_open_flag(date_str: str) -> bool | None:
    """캐시된 개장일 여부. 해당 날짜가 캐시에 없으면 None(호출부가 하드코딩 표로 폴백)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT is_open FROM market_holidays WHERE date = ?", (date_str,)
        ).fetchone()
        return None if row is None else bool(row["is_open"])
    finally:
        conn.close()


def get_market_holiday_meta() -> dict:
    """휴장일 캐시 메타 — 건수·커버 범위·마지막 조회 시각.

    스케줄러가 "1일 1회" 제약을 지키며 갱신 필요 여부를 판단하는 데 쓴다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS count, MIN(date) AS min_date, MAX(date) AS max_date, "
            "MAX(fetched_at) AS fetched_at FROM market_holidays"
        ).fetchone()
        return dict(row)
    finally:
        conn.close()


# ────────────────────────────────────────────
# 판정 전환 알림 이력
# ────────────────────────────────────────────

# 보존 상한. 개인용 앱이라 이력이 무한히 자라면 DB 만 커진다. 넘으면 오래된 것부터 지운다.
# 관심종목 수십 개 × 하루 몇 건이면 수백 건으로 몇 주가 덮인다.
ALERT_HISTORY_MAX_ROWS = 500


def insert_decision_alert_history(rows: list[dict]) -> None:
    """발송 성공한 전환을 이력에 남긴다. 빈 리스트면 아무 것도 하지 않는다.

    `channels` 는 **성공한 채널만** 콤마로 이어 넘긴다(호출부 책임).
    """
    if not rows:
        return
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "INSERT INTO decision_alert_history "
            "(code, name, view_kind, before_view, after_view, close, change_pct, channels) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    _normalize_code(r["code"]), r["name"], r["view_kind"],
                    r["before_view"], r["after_view"],
                    r.get("close"), r.get("change_pct"), r["channels"],
                )
                for r in rows
            ],
        )
        # 상한 초과분 정리. id 기준이라 삽입 순서가 곧 시간 순서다(notified_at 은
        # 초 단위라 같은 사이클 내 동시 삽입을 구분하지 못한다).
        cap = max(1, int(ALERT_HISTORY_MAX_ROWS))
        conn.execute(
            "DELETE FROM decision_alert_history WHERE id <= ("
            "  SELECT MAX(id) FROM decision_alert_history"
            ") - ?",
            (cap,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_decision_alert_history(limit: int = 100) -> list[dict]:
    """최신순 알림 이력. limit 은 1~500 으로 조인다.

    0·음수를 그대로 LIMIT 에 넘기면 SQLite 가 전체를 돌려준다(LIMIT -1 = 무제한) —
    페이지 크기를 실수로 0 으로 준 호출이 전체 스캔이 되지 않게 막는다.
    """
    safe_limit = max(1, min(int(limit), 500))
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, notified_at, code, name, view_kind, before_view, after_view, "
            "close, change_pct, channels "
            "FROM decision_alert_history ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ────────────────────────────────────────────
# 판정 전환 알림 기준선
# ────────────────────────────────────────────

def get_decision_alert_state() -> dict[tuple[str, str], dict]:
    """{(code, view_kind): {view, fund_mask, source, notified_at, updated_at}}.

    사이클마다 종목 수만큼 SELECT 하지 않도록 전량을 한 번에 읽는다(관심종목 규모가
    수십 건이라 전량 읽기가 더 싸다).
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT code, view_kind, view, fund_mask, source, notified_at, updated_at "
            "FROM decision_alert_state"
        ).fetchall()
        return {
            (r["code"], r["view_kind"]): {
                "view": r["view"],
                "fund_mask": int(r["fund_mask"]),
                "source": r["source"],
                "notified_at": r["notified_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        }
    finally:
        conn.close()


def upsert_decision_alert_state(rows: list[dict]) -> int:
    """[{code, view_kind, view, fund_mask, source, notified: bool}, ...] 를 upsert.

    세 가지 보호 장치가 이 한 문장에 들어 있다:

    1. `WHERE EXISTS (... watchlist ... is_active = 1)` — **활성 관심종목만** 기준선을 갖는다.
       수집 사이클은 시작 시점의 watchlist 스냅샷으로 돌고 사이클 **끝**에 이 함수를 부르므로,
       그 사이에 라우터 스레드가 종목을 지우면 방금 지운 기준선이 되살아난다(그 행은
       notified_at=NULL 이라 쿨다운도 안 걸려 재추가 시 헛알림이 된다). 단일 statement 안의
       원자적 검사라 그 레이스가 구조적으로 닫힌다.
    2. `notified_at = COALESCE(...)` — 무음 시딩이 기존 발송 시각을 밀지 않는다(쿨다운 기준 보존).
    3. `source = COALESCE(...)` — 출처를 알 수 없는 사이클(None)이 저장된 'kis'/'yfinance' 를
       지우지 않는다. 지우면 다음 사이클에 NULL→'kis' 가 또 입력 변화로 잡혀 2차 무음 재시딩이 난다.

    fund_mask 는 bool 로 강제하지 않는다 — 0~7 비트마스크를 1 로 접으면 게이트가 무력해진다.
    """
    if not rows:
        return 0

    now = datetime.now(timezone.utc).strftime(_UTC_TS_FORMAT)
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO decision_alert_state
                (code, view_kind, view, fund_mask, source, notified_at, updated_at)
            SELECT ?, ?, ?, ?, ?, ?, ?
             WHERE EXISTS (SELECT 1 FROM watchlist WHERE code = ? AND is_active = 1)
            ON CONFLICT(code, view_kind) DO UPDATE SET
                view = excluded.view,
                fund_mask = excluded.fund_mask,
                source = COALESCE(excluded.source, decision_alert_state.source),
                notified_at = COALESCE(excluded.notified_at, decision_alert_state.notified_at),
                updated_at = excluded.updated_at
            """,
            [
                (
                    r["code"], r["view_kind"], r["view"],
                    int(r.get("fund_mask") or 0),
                    r.get("source"),
                    now if r.get("notified") else None,
                    now,
                    r["code"],  # WHERE EXISTS 용 — 활성 관심종목 확인
                )
                for r in rows
            ],
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def delete_decision_alert_state(code) -> int:
    """한 종목의 알림 기준선을 삭제. 관심종목에서 제거할 때 함께 지운다."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM decision_alert_state WHERE code = ?", (_normalize_code(code),)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ────────────────────────────────────────────
# 모의투자(Paper Trading) — 개인용 단일 계좌(id=1)
# ────────────────────────────────────────────

class InvalidOrderError(Exception):
    """수량·가격이 유효하지 않은 주문."""


class InsufficientFundsError(Exception):
    """현금 잔액 부족(매수) 또는 보유 수량 부족(매도)."""


def _ensure_account(conn: sqlite3.Connection, seed: float) -> None:
    """계좌가 없으면 시드머니로 생성(멱등). 호출부에서 트랜잭션/커밋 관리."""
    conn.execute(
        "INSERT OR IGNORE INTO paper_account (id, cash, seed) VALUES (1, ?, ?)",
        (seed, seed),
    )


def _account_snapshot(conn: sqlite3.Connection) -> dict:
    acct = conn.execute(
        "SELECT cash, seed FROM paper_account WHERE id = 1"
    ).fetchone()
    holdings = conn.execute(
        "SELECT code, name, qty, avg_cost FROM paper_holdings WHERE qty > 0 ORDER BY code"
    ).fetchall()
    # 실현손익 누적 = 매도에서 확정된 손익의 합. 마이그레이션 이전 거래는 realized_pnl 이
    # NULL 이라 SUM 에서 자연히 제외된다(0 으로 세지 않는다 — 모르는 값이다).
    realized = conn.execute(
        "SELECT COALESCE(SUM(realized_pnl), 0.0) AS total FROM paper_trades"
    ).fetchone()
    # 실현손익을 계산할 수 없는 과거 거래가 남아 있는지. 있으면 실현/미실현 분해가
    # 총손익과 맞지 않으므로 화면이 그 사실을 알려야 한다.
    unknown = conn.execute(
        "SELECT COUNT(*) AS n FROM paper_trades "
        "WHERE side = 'sell' AND realized_pnl IS NULL"
    ).fetchone()
    return {
        "cash": acct["cash"] if acct else 0.0,
        "seed": acct["seed"] if acct else 0.0,
        "holdings": [dict(h) for h in holdings],
        "realized_pnl": round(realized["total"], 2),
        "realized_unknown_trades": unknown["n"],
    }


def get_paper_account(seed_default: float) -> dict:
    """가상 계좌 스냅샷(현금·시드·보유목록). 없으면 시드로 생성."""
    conn = get_connection()
    try:
        _ensure_account(conn, seed_default)
        conn.commit()
        return _account_snapshot(conn)
    finally:
        conn.close()


def get_paper_trades(limit: int = 100) -> list[dict]:
    safe_limit = max(1, min(int(limit), 500))
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, ts, code, name, side, qty, price, amount, "
            "price_source, market_status, realized_pnl "
            "FROM paper_trades ORDER BY id DESC LIMIT ?",
            (safe_limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


PRICE_SOURCES = ("market", "book")


def execute_paper_order(
    code, name: str, side: str, qty: int, price: float, seed_default: float,
    *, price_source: str, market_status: str | None = None,
) -> dict:
    """시장가 즉시 체결 시뮬레이션. 잔액/보유 검증부터 갱신까지 단일 IMMEDIATE
    트랜잭션으로 원자화해 동시 주문 TOCTOU(초과매수·음수잔액·초과매도)를 방지한다.
    체결 성공 시 갱신된 계좌 스냅샷 반환.

    `price_source` 는 필수 키워드다 — 기본값을 주면 호출부가 잊었을 때 조용히
    'market' 으로 기록돼, 장부가 대체 체결이 실제 시장가 체결로 위장된다.
    `realized_pnl`(매도)은 **이 트랜잭션 안에서** 계산한다. 평균단가는 체결 직전에만
    정확히 알 수 있고, 나중에 거래내역만으로 되계산하려면 평균단가 이력이 필요해 불가능하다.
    """
    normalized = _normalize_code(code)
    if side not in ("buy", "sell"):
        raise InvalidOrderError(f"잘못된 주문 유형: {side}")
    if price_source not in PRICE_SOURCES:
        raise InvalidOrderError(f"알 수 없는 체결가 출처: {price_source}")
    if not isinstance(qty, int) or qty <= 0:
        raise InvalidOrderError("수량은 1 이상의 정수여야 합니다.")
    price_f = float(price)
    if price_f <= 0:
        raise InvalidOrderError("체결 가격이 유효하지 않습니다.")

    amount = round(price_f * qty, 2)

    conn = get_connection()
    try:
        # BEGIN IMMEDIATE: 쓰기 락을 즉시 잡아 read-modify-write 를 직렬화
        conn.execute("BEGIN IMMEDIATE")
        _ensure_account(conn, seed_default)

        acct = conn.execute("SELECT cash FROM paper_account WHERE id = 1").fetchone()
        cash = acct["cash"]
        holding = conn.execute(
            "SELECT qty, avg_cost FROM paper_holdings WHERE code = ?", (normalized,)
        ).fetchone()

        realized_pnl = None
        if side == "buy":
            if amount > cash:
                raise InsufficientFundsError(
                    f"현금 잔액 부족: 필요 {amount:,.0f}원 / 보유 {cash:,.0f}원"
                )
            new_cash = cash - amount
            if holding is None:
                new_qty, new_avg = qty, price_f
            else:
                total_qty = holding["qty"] + qty
                new_avg = (holding["avg_cost"] * holding["qty"] + amount) / total_qty
                new_qty = total_qty
            conn.execute(
                "INSERT INTO paper_holdings (code, name, qty, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, datetime('now')) "
                "ON CONFLICT(code) DO UPDATE SET qty = ?, avg_cost = ?, name = ?, "
                "updated_at = datetime('now')",
                (normalized, name, new_qty, new_avg, new_qty, new_avg, name),
            )
        else:  # sell
            held = holding["qty"] if holding else 0
            if qty > held:
                raise InsufficientFundsError(
                    f"보유 수량 부족: 매도 {qty}주 / 보유 {held}주"
                )
            new_cash = cash + amount
            # 실현손익 = (체결가 - 매도 시점 평균단가) * 수량. 평균이동원가 방식이므로
            # 부분 매도 후에도 남은 보유의 평균단가는 그대로다(원가 basis 가 비례 감소).
            realized_pnl = round((price_f - holding["avg_cost"]) * qty, 2)
            remaining = held - qty
            if remaining > 0:
                conn.execute(
                    "UPDATE paper_holdings SET qty = ?, updated_at = datetime('now') "
                    "WHERE code = ?",
                    (remaining, normalized),
                )
            else:
                conn.execute("DELETE FROM paper_holdings WHERE code = ?", (normalized,))

        conn.execute(
            "UPDATE paper_account SET cash = ?, updated_at = datetime('now') WHERE id = 1",
            (new_cash,),
        )
        conn.execute(
            "INSERT INTO paper_trades "
            "(code, name, side, qty, price, amount, price_source, market_status, realized_pnl) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (normalized, name, side, qty, price_f, amount,
             price_source, market_status, realized_pnl),
        )
        snapshot = _account_snapshot(conn)
        conn.commit()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_paper_account(seed: float) -> dict:
    """가상 계좌 초기화 — 보유·거래내역 삭제 후 현금을 시드로 리셋."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM paper_holdings")
        conn.execute("DELETE FROM paper_trades")
        conn.execute(
            "INSERT INTO paper_account (id, cash, seed, updated_at) "
            "VALUES (1, ?, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET cash = ?, seed = ?, updated_at = datetime('now')",
            (seed, seed, seed, seed),
        )
        snapshot = _account_snapshot(conn)
        conn.commit()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
