"""KRX(한국거래소) 휴장일 인지.

평일이라도 아래 날짜는 휴장이므로 수집을 idle 로 둔다(불필요 조회 방지 + "휴장" 배지 근거).

주의: 음력 연휴(설·추석)·대체공휴일·임시공휴일·노동절·연말 폐장일은 해마다 바뀌므로
이 표는 **매년 갱신**해야 한다. 표에 없는 미래 연도는 '고정 공휴일 + 주말'만 인지하므로
음력/대체 휴장을 놓칠 수 있다(그 경우 불필요 조회가 조금 생길 뿐 데이터 정확성엔 무해).
"""
from datetime import date, datetime, time, timedelta

# YYYY-MM-DD (Asia/Seoul) — 고정 공휴일 + 설/추석 연휴 + 대체공휴일 + 노동절(5/1, 증시휴장)
# + 연말 폐장일(12/31). 2025~2026 큐레이션.
_KRX_HOLIDAYS: set[str] = {
    # 2025
    "2025-01-01", "2025-01-28", "2025-01-29", "2025-01-30", "2025-03-01", "2025-03-03",
    "2025-05-01", "2025-05-05", "2025-05-06", "2025-06-06", "2025-08-15", "2025-10-03",
    "2025-10-06", "2025-10-07", "2025-10-08", "2025-10-09", "2025-12-25", "2025-12-31",
    # 2026
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-01", "2026-03-02",
    "2026-05-01", "2026-05-05", "2026-05-25", "2026-06-06", "2026-08-15", "2026-08-17",
    "2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-05", "2026-10-09",
    "2026-12-25", "2026-12-31",
}

# 큐레이션이 끝난 마지막 연도. 이 연도를 넘어가면 음력 연휴·대체공휴일을 알 수 없으므로
# is_year_covered() 가 False 를 돌려주고, 호출부는 "달력만 믿지 말라"는 경고를 남긴다.
# (여기에 검증되지 않은 미래 음력 날짜를 추측해 넣으면 실제 거래일을 휴장으로 오판해
#  수집을 건너뛰는, 훨씬 나쁜 실패로 바뀐다 → 추측 대신 커버리지를 노출한다.)
TABLE_MAX_YEAR = 2026

# 표에 없는 미래 연도라도 인지 가능한 고정(양력) 공휴일 (MM-DD).
_FIXED_MMDD: set[str] = {
    "01-01",  # 신정
    "03-01",  # 삼일절
    "05-01",  # 노동절(증시 휴장)
    "05-05",  # 어린이날
    "06-06",  # 현충일
    "08-15",  # 광복절
    "10-03",  # 개천절
    "10-09",  # 한글날
    "12-25",  # 성탄절
    "12-31",  # 연말 폐장
}


def _key(d) -> str:
    if isinstance(d, str):
        return d[:10]
    return d.strftime("%Y-%m-%d")


def is_holiday(d) -> bool:
    """해당 날짜가 KRX 휴장일이면 True(주말은 별도 — is_trading_day 에서 처리)."""
    key = _key(d)
    return key in _KRX_HOLIDAYS or key[5:] in _FIXED_MMDD


def is_year_covered(d) -> bool:
    """해당 날짜의 연도가 큐레이션된 휴장일 표(_KRX_HOLIDAYS) 범위 안이면 True.

    False 면 고정 양력 공휴일 + 주말만 인지 가능한 상태다 — 즉 설·추석·대체공휴일을
    놓칠 수 있으므로, 달력 판정만으로 데이터 신선도를 단정하면 안 된다(호출부는 실제
    데이터의 거래일(bar_date)로 교차 검증할 것).
    """
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.year <= TABLE_MAX_YEAR


def _cached_open_flag(d: date) -> bool | None:
    """KIS 국내휴장일조회(CTCA0903R) 결과 캐시를 조회. 없거나 실패하면 None.

    이 캐시가 있으면 **그것이 권위 있는 답**이다(공식 개장일 여부). 하드코딩 표는 자격증명이
    없거나 캐시에 없는 날짜를 위한 폴백으로만 남는다.

    지연 import + 전체 예외 격리: market_calendar 는 DB 없이도 동작해야 한다(크론은
    GitHub Actions 러너에서 매번 새로 클론되므로 DB가 비어 있다).
    """
    try:
        import db

        return db.get_market_open_flag(d.isoformat())
    except Exception:
        return None


def is_trading_day(d) -> bool:
    """거래일(개장일)이면 True.

    판단 순서:
      1) KIS 휴장일 캐시(공식) — 있으면 이 값을 그대로 신뢰한다.
      2) 하드코딩 표 + 주말 — 캐시에 없는 날짜(자격증명 없음·미래 구간·크론 환경)의 폴백.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])

    cached = _cached_open_flag(d)
    if cached is not None:
        return cached

    return d.weekday() < 5 and not is_holiday(d)


def calendar_source(d) -> str:
    """이 날짜의 판정 근거 — "kis"(공식 캐시) 또는 "builtin"(하드코딩 표).

    화면에서 "공휴일 판정이 정확하지 않을 수 있습니다" 경고를 낼지 결정하는 데 쓴다.
    """
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return "kis" if _cached_open_flag(d) is not None else "builtin"


# ────────────────────────────────────────────
# 정규장 세션 시각 (KRX)
#
# 09:00 개장 ~ 15:30 마감. 이 값은 **화면에 표시하는 시장 상태** 기준이다.
# 수집 루프의 창(server/services/collector.py 의 09:00~15:40)과 일부러 다르다 —
# 그쪽은 마감 직후 종가가 확정될 여유를 둔 '수집 창'이고, 여기는 사용자에게 보여주는
# '실제 장 운영 시간'이다. 두 값을 하나로 합치면 어느 한쪽이 틀리게 된다.
# ────────────────────────────────────────────

SESSION_OPEN = time(9, 0)
SESSION_CLOSE = time(15, 30)

# 상태 코드 → 화면 표시 라벨. 프론트가 문자열을 복제하지 않도록 서버가 함께 내려준다.
_STATUS_LABELS = {
    "pre": "장전",
    "open": "장중",
    "closed": "장마감",
    "holiday": "휴장",
}

# 미래로 거래일을 찾을 때의 탐색 상한(연휴가 길어도 이 안에 반드시 거래일이 있다).
_SEARCH_LIMIT_DAYS = 30


def previous_trading_day(d) -> date:
    """d 이전(d 제외)의 가장 최근 거래일."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    cursor = d - timedelta(days=1)
    for _ in range(_SEARCH_LIMIT_DAYS):
        if is_trading_day(cursor):
            return cursor
        cursor -= timedelta(days=1)
    return cursor


def next_trading_day(d) -> date:
    """d 이후(d 제외)의 가장 이른 거래일."""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    cursor = d + timedelta(days=1)
    for _ in range(_SEARCH_LIMIT_DAYS):
        if is_trading_day(cursor):
            return cursor
        cursor += timedelta(days=1)
    return cursor


def market_status(now: datetime) -> dict:
    """현재 시장 상태와 세션 경계를 계산한다(외부 조회 없음, 순수 계산).

    반환:
      status  — "pre" | "open" | "closed" | "holiday"
      label   — 화면 표시용 한국어 라벨
      session_open / session_close — **다음에 의미 있는 세션**의 경계(ISO8601).
          장전·장중이면 오늘 세션, 장마감·휴장이면 다음 거래일 세션. 프론트가 이 값으로
          "마감까지 N시간 M분" / "개장까지 …" 카운트다운을 로컬에서 계산한다(초당 폴링 불필요).
      reference_trading_day — 지금 화면에 보이는 시세가 속한 거래일.
          휴장·장전이면 직전 거래일이다 → "최근 거래일 기준" 안내의 근거(신선도 오해 방지).
      calendar_covered — 이 날짜의 판정을 신뢰할 수 있는지.
          KIS 공식 휴장일 캐시가 있으면 True. 없으면 하드코딩 표 범위(TABLE_MAX_YEAR) 안일
          때만 True — 범위 밖이면 음력 연휴를 놓칠 수 있으므로 화면이 단정하지 않는다.
      calendar_source — "kis"(공식 캐시) | "builtin"(하드코딩 표)

    now 는 tz-aware 여야 한다(호출부가 Asia/Seoul 로 만들어 넘긴다).
    """
    today = now.date()
    trading_today = is_trading_day(today)

    if not trading_today:
        status = "holiday"
        session_day = next_trading_day(today)
        reference_day = previous_trading_day(today)
    elif now.time() < SESSION_OPEN:
        status = "pre"
        session_day = today
        # 개장 전에는 아직 오늘 시세가 없다 → 직전 거래일 기준.
        reference_day = previous_trading_day(today)
    elif now.time() <= SESSION_CLOSE:
        status = "open"
        session_day = today
        reference_day = today
    else:
        status = "closed"
        session_day = next_trading_day(today)
        reference_day = today

    tz = now.tzinfo
    source = calendar_source(today)
    return {
        "status": status,
        "label": _STATUS_LABELS[status],
        "server_time": now.isoformat(),
        "session_open": datetime.combine(session_day, SESSION_OPEN, tzinfo=tz).isoformat(),
        "session_close": datetime.combine(session_day, SESSION_CLOSE, tzinfo=tz).isoformat(),
        "session_date": session_day.isoformat(),
        "reference_trading_day": reference_day.isoformat(),
        # 공식 캐시가 있으면 연도 범위와 무관하게 신뢰할 수 있다.
        "calendar_covered": source == "kis" or is_year_covered(today),
        "calendar_source": source,
    }
