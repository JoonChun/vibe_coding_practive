"""server/services/whatif.py — "그날의 나" What-if 손익·봇 판정 서비스 테스트.

실 네트워크·실 DB는 전혀 열지 않는다 — candles.get_candles/get_index_candles 를
monkeypatch로 가짜 일봉만 주입해 whatif.compute_whatif()의 순수 계산 로직만 검증한다
(whatif.py 자신은 pandas 연산 외에 별도 I/O가 없어 이 두 함수만 막으면 충분히 격리된다).

시간 의존성: 캔들 t 값은 whatif._requested_epoch/_epoch_to_date_str 와 동일한 규칙
(KST 자정 기준 Unix epoch)을 테스트 자체 헬퍼(_t)로 독립 재현한 값이다 — 실제 시각
(datetime.now 등)에 전혀 의존하지 않아 결정적이다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from server.schemas import WhatIfResponse
from server.services import candles as candles_mod
from server.services import whatif

_KST = ZoneInfo("Asia/Seoul")
_CODE = "005930"

_LONG_VIEW_VOCAB = {"강력매수", "매수", "관망", "매도", "강력매도", "데이터부족"}


# ────────────────────────────────────────────
# 합성 캔들 헬퍼
# ────────────────────────────────────────────

def _t(date_str: str) -> int:
    """'YYYY-MM-DD' → KST 자정 기준 Unix epoch(초). whatif._requested_epoch와 동일 규칙을
    테스트가 독립적으로(프로덕션 코드에 기대지 않고) 재현한 것 — 같은 문자열이면 항상
    같은 epoch이라 whatif._find_buy_index의 t<=requested_epoch 비교와 그대로 맞아떨어진다."""
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=_KST).timestamp())


def _item(date_str: str, close: float, volume: float = 1000.0) -> dict:
    return {
        "t": _t(date_str),
        "open": close + 0.1,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": volume,
    }


def _bdate_strs(start: str, n: int) -> list[str]:
    """평일(주말 제외)만 골라 n개의 'YYYY-MM-DD' 문자열을 생성 — 실제 거래일과 유사한
    간격(주말=휴장일)을 흉내낸다. 공휴일까지는 반영하지 않지만 매수일 스냅(휴장일→직전
    거래일) 검증에는 주말만으로 충분하다."""
    import pandas as pd
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start=start, periods=n)]


@pytest.fixture(autouse=True)
def _default_no_index_history(monkeypatch):
    """대부분의 케이스는 코스피 병치를 다루지 않으므로 기본값으로 빈 이력을 준다.
    whatif.py가 실제로 타는 호출 경로(candles.get_index_candles)는 그대로 살려두되,
    네트워크 접근 없이 빈 리스트만 돌려줘 kospi=None 경로를 항상 안전하게 통과시킨다."""
    monkeypatch.setattr(candles_mod, "get_index_candles", lambda count: [])
    yield


def _patch_stock(monkeypatch, items: list[dict], source: str | None = "kis") -> None:
    monkeypatch.setattr(candles_mod, "get_candles", lambda code, tf, count: {"items": items, "source": source})


# ────────────────────────────────────────────
# 1. 매수일 채택 — 거래일 그대로 채택 / 휴장일 직전 거래일 스냅
# ────────────────────────────────────────────

_FIVE_DAYS = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]  # 화~월(주말 제외)
_FIVE_CLOSES = [100.0, 101.0, 102.0, 103.0, 104.0]
_FIVE_ITEMS = [_item(d, c) for d, c in zip(_FIVE_DAYS, _FIVE_CLOSES)]


def test_buy_date_exact_match_adopts_requested_trading_day(monkeypatch):
    _patch_stock(monkeypatch, _FIVE_ITEMS)

    result = whatif.compute_whatif(_CODE, "2024-01-04", 1_000_000)

    assert result["buy_date"] == "2024-01-04"
    assert result["buy_price"] == 102.0
    assert result["error"] is None


def test_buy_date_snaps_to_previous_trading_day_on_holiday(monkeypatch):
    """2024-01-06은 토요일(가짜 이력에 없는 날짜) — 직전 거래일(01-05, 금)로 스냅돼야 한다."""
    _patch_stock(monkeypatch, _FIVE_ITEMS)

    result = whatif.compute_whatif(_CODE, "2024-01-06", 1_000_000)

    assert result["requested_date"] == "2024-01-06"
    assert result["buy_date"] == "2024-01-05"
    assert result["buy_price"] == 103.0
    assert result["error"] is None


# ────────────────────────────────────────────
# 2. 손익 산수 — buy_price 10,000 · current 25,000 · 원금 1,000,000
# ────────────────────────────────────────────

def test_profit_calc_exact_arithmetic_and_rounding(monkeypatch):
    items = [_item("2024-01-02", 10_000.0), _item("2024-01-08", 25_000.0)]
    _patch_stock(monkeypatch, items)

    result = whatif.compute_whatif(_CODE, "2024-01-02", 1_000_000)

    assert result["buy_price"] == 10_000.0
    assert result["current_price"] == 25_000.0
    assert result["shares"] == 100.0                 # amount/buy_price, 소수 4자리 반올림
    assert result["eval_amount"] == 2_500_000         # 정수 반올림
    assert result["profit"] == 1_500_000              # 정수 반올림
    assert result["return_pct"] == 150.0              # 소수 2자리 반올림
    assert result["multiple"] == 2.5                  # 소수 1자리 반올림


# ────────────────────────────────────────────
# 3. 코스피 병치 — 동일 산식 재사용 / 지수 이력 없음(빈 리스트·예외) 시 kospi=null(크래시 금지)
# ────────────────────────────────────────────

_KOSPI_STOCK_ITEMS = [_item("2024-01-02", 10_000.0), _item("2024-01-08", 12_000.0)]
_KOSPI_INDEX_ITEMS = [_item("2024-01-02", 2_500.0), _item("2024-01-08", 3_000.0)]


def test_kospi_side_computed_with_same_pnl_rule(monkeypatch):
    _patch_stock(monkeypatch, _KOSPI_STOCK_ITEMS)
    monkeypatch.setattr(candles_mod, "get_index_candles", lambda count: _KOSPI_INDEX_ITEMS)

    result = whatif.compute_whatif(_CODE, "2024-01-02", 500_000)

    assert result["kospi"] == {
        "buy_price": 2_500.0,
        "current_price": 3_000.0,
        "eval_amount": 600_000,
        "profit": 100_000,
        "return_pct": 20.0,
        "multiple": 1.2,
    }
    # 종목 쪽도 같은 산식으로 정상 계산돼야 한다(코스피 병치가 종목 계산을 침범하지 않음).
    assert result["eval_amount"] == 600_000
    assert result["return_pct"] == 20.0


def test_kospi_null_when_index_history_empty(monkeypatch):
    _patch_stock(monkeypatch, _KOSPI_STOCK_ITEMS)
    # 기본 autouse 픽스처가 이미 get_index_candles → [] 로 고정돼 있음(명시적으로 재확인).
    monkeypatch.setattr(candles_mod, "get_index_candles", lambda count: [])

    result = whatif.compute_whatif(_CODE, "2024-01-02", 500_000)

    assert result["kospi"] is None
    assert result["error"] is None  # 종목 응답 자체는 정상(크래시 금지)


def test_kospi_null_when_index_fetch_raises(monkeypatch):
    """crawler 예외 등으로 get_index_candles 자체가 예외를 던져도 whatif 응답 전체가
    죽지 않고 kospi=null 로만 처리돼야 한다(whatif.py의 try/except 경로)."""
    _patch_stock(monkeypatch, _KOSPI_STOCK_ITEMS)

    def _raise(count):
        raise RuntimeError("코스피 지수 조회 실패(시뮬레이션)")

    monkeypatch.setattr(candles_mod, "get_index_candles", _raise)

    result = whatif.compute_whatif(_CODE, "2024-01-02", 500_000)

    assert result["kospi"] is None
    assert result["error"] is None
    assert result["eval_amount"] == 600_000  # 종목 손익은 그대로 정상


# ────────────────────────────────────────────
# 4. 그날 봇 판정 슬라이스 — 매수일 이후 데이터가 판정에 새어들지 않는지
# ────────────────────────────────────────────
# 매수일까지 90봉은 하락 추세(사인파 눌림을 얹은 완만한 하락 — RSI가 0으로 붕괴하는
# 순수 단조하락 대신 실제 시장처럼 등락 섞인 하락이 되도록), 이후 30봉은 급등(+3/봉).
# 아래 수치(buy_price/current_price/bot_judgment)는 이 파일 작성 중 실제로
# compute_whatif()를 호출해 확인한 값(실측 — 임의 추정 아님).

def _declining_then_rally_items() -> tuple[list[dict], str]:
    import math

    pre_n, post_n = 90, 30
    slope, amp, period, post_slope = 0.3, 3.0, 6, 3.0
    dates = _bdate_strs("2024-01-02", pre_n + post_n)

    closes = [100.0 - i * slope + amp * math.sin(2 * math.pi * i / period) for i in range(pre_n)]
    last_pre = closes[-1]
    closes += [last_pre + j * post_slope for j in range(post_n)]

    items = [_item(d, c) for d, c in zip(dates, closes)]
    buy_date_str = dates[pre_n - 1]
    return items, buy_date_str


def test_bot_judgment_uses_only_data_up_to_buy_date_not_future_rally(monkeypatch):
    items, buy_date_str = _declining_then_rally_items()
    # 픽스처 구성상 매수일은 인덱스 89 — 그 뒤 90~은 급등 구간이라, 판정이 급등을
    # 반영하면 미래 데이터가 샌 것이다(아래 assert 가 그것을 잡는다).
    _patch_stock(monkeypatch, items)

    result = whatif.compute_whatif(_CODE, buy_date_str, 1_000_000)

    # 매수일 시점(하락 추세 반영) 판정 — 실측값.
    assert result["buy_date"] == "2024-05-06"
    assert result["buy_price"] == 70.7
    assert result["bot_judgment"] == {
        "long_view": "매도",
        "macd_1d": "매도구간",
        "rsi_1d": "중립",
        "pullback_status": "추세아님",
        "note": whatif._BOT_NOTE,
    }
    assert result["bot_judgment"]["long_view"] in _LONG_VIEW_VOCAB

    # 이후 급등(post-rally)이 실제로 신호를 뒤집을 만큼 크다는 것을 별도로 확인 —
    # 슬라이스 없이(버그 시나리오) 전체 이력으로 판정했다면 완전히 다른(매수 쪽) 신호가
    # 나왔을 것임을 whatif._compute_bot_judgment를 직접 호출해 대조한다. 이 대조가
    # 다르게 나와야만 위 assert가 "우연히 같은 값"이 아니라 실제로 매수일 슬라이스가
    # 적용된 결과임을 보증한다.
    bugged_full_series = whatif._compute_bot_judgment(items, len(items) - 1)
    assert bugged_full_series["macd_1d"] != result["bot_judgment"]["macd_1d"]
    assert bugged_full_series["rsi_1d"] != result["bot_judgment"]["rsi_1d"]
    assert bugged_full_series["pullback_status"] != result["bot_judgment"]["pullback_status"]

    # 손익(현재가)은 매수일 슬라이스와 무관하게 최신(전체 이력 마지막) 종가를 그대로 써야 함
    # (buy_price/current_price는 _calc_side에서 소수 2자리로 반올림되므로 그만큼만 비교).
    assert result["current_price"] == round(items[-1]["close"], 2)


# ────────────────────────────────────────────
# 5. 재무 제외 — bot_judgment.note 고정 문구
# ────────────────────────────────────────────

def test_bot_judgment_note_is_fixed_financial_exclusion_text(monkeypatch):
    items = [_item("2024-01-02", 10_000.0), _item("2024-01-08", 12_000.0)]
    _patch_stock(monkeypatch, items)

    result = whatif.compute_whatif(_CODE, "2024-01-02", 1_000_000)

    assert result["bot_judgment"]["note"] == "가격 기반 지표만 — PER/PBR/ROE는 과거 재현 불가로 제외"
    assert result["bot_judgment"]["note"] == whatif._BOT_NOTE


# ────────────────────────────────────────────
# 6. 엣지 — 상장 전/조회 범위 밖(요청일 이전 데이터 0건)
# ────────────────────────────────────────────

@pytest.mark.parametrize(
    "items, source, expected_source",
    [
        pytest.param([], None, None, id="no_data_at_all"),
        pytest.param(_FIVE_ITEMS, "kis", "kis", id="data_exists_but_all_after_requested_date"),
    ],
)
def test_no_data_before_requested_date_returns_error_with_null_fields(
    monkeypatch, items, source, expected_source
):
    _patch_stock(monkeypatch, items, source=source)

    # 두 서브케이스 모두 "요청일 이전 데이터 0건"에 해당하는 날짜를 쓴다:
    # - 완전 무이력이면 아무 날짜나 이전 데이터가 없고
    # - _FIVE_ITEMS(2024-01-02 시작)에는 그보다 앞선 2024-01-01을 요청.
    requested_date = "2024-01-01" if items else "2024-01-04"

    result = whatif.compute_whatif(_CODE, requested_date, 1_000_000)

    assert result["error"] == "해당 날짜 이전 데이터 없음 — 상장 전이거나 조회 범위(약 4년) 밖"
    assert result["source"] == expected_source
    for field in (
        "buy_date", "buy_price", "shares", "current_date", "current_price",
        "eval_amount", "profit", "return_pct", "multiple", "kospi", "bot_judgment",
    ):
        assert result[field] is None, f"{field} 는 데이터 없음 응답에서 null 이어야 함"
    assert result["code"] == _CODE
    assert result["requested_date"] == requested_date
    assert result["amount"] == 1_000_000


def test_invalid_date_format_returns_error_without_touching_candles(monkeypatch):
    """방어적 파싱 실패 경로 — 라우터가 형식 검증을 선행한다는 전제지만, 이 함수
    자체도 잘못된 형식을 받으면 candles.get_candles 조차 호출하지 않고 즉시 에러를
    반환해야 한다."""
    calls = []
    monkeypatch.setattr(
        candles_mod, "get_candles",
        lambda code, tf, count: calls.append(1) or {"items": [], "source": None},
    )

    result = whatif.compute_whatif(_CODE, "2024/01/02", 1_000_000)

    assert calls == []  # candles 조회 자체가 발생하지 않아야 함
    assert result["error"] == "날짜 형식 오류(YYYY-MM-DD): 2024/01/02"
    assert result["buy_price"] is None


# ────────────────────────────────────────────
# 7. 엣지 — 이력 짧아 판정 불가(매수일까지 봉 10개뿐)해도 손익 계산은 정상
# ────────────────────────────────────────────

def test_short_history_bot_judgment_insufficient_but_pnl_computed(monkeypatch):
    dates10 = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08",
               "2024-01-09", "2024-01-10", "2024-01-11", "2024-01-12", "2024-01-15"]
    closes10 = [50.0 + i for i in range(10)]  # 매수일(마지막, 2024-01-15) 종가 59
    extra_items = [_item("2024-01-16", 70.0), _item("2024-01-17", 80.0)]  # 매수일 이후(현재가 갱신용)

    items = [_item(d, c) for d, c in zip(dates10, closes10)] + extra_items
    _patch_stock(monkeypatch, items)

    result = whatif.compute_whatif(_CODE, "2024-01-15", 1_000_000)

    # 손익은 정상 계산(매수일 이후 현재가 반영).
    assert result["buy_date"] == "2024-01-15"
    assert result["buy_price"] == 59.0
    assert result["current_price"] == 80.0
    assert result["shares"] == 16_949.1525
    assert result["eval_amount"] == 1_355_932
    assert result["profit"] == 355_932
    assert result["return_pct"] == 35.59
    assert result["multiple"] == 1.4
    assert result["error"] is None

    # 봇 판정 지표는 전부 "데이터부족"(10봉 < MACD 최소 35봉 / RSI 최소 15봉 / 눌림목 65봉).
    bot = result["bot_judgment"]
    assert bot["macd_1d"] == "데이터부족"
    assert bot["rsi_1d"] == "데이터부족"
    assert bot["pullback_status"] == "데이터부족"
    assert bot["long_view"] == "데이터부족"


# ────────────────────────────────────────────
# 8. Pydantic 계약 — 성공/에러 두 결과 모두 WhatIfResponse(**result) 파싱 통과
# ────────────────────────────────────────────

def test_success_result_parses_as_whatif_response(monkeypatch):
    items = [_item("2024-01-02", 10_000.0), _item("2024-01-08", 12_000.0)]
    _patch_stock(monkeypatch, items)
    monkeypatch.setattr(candles_mod, "get_index_candles", lambda count: _KOSPI_INDEX_ITEMS)

    result = whatif.compute_whatif(_CODE, "2024-01-02", 500_000)

    parsed = WhatIfResponse(**result)
    assert parsed.error is None
    assert parsed.buy_price == 10_000.0
    assert parsed.kospi is not None
    assert parsed.kospi.eval_amount == 600_000
    assert parsed.bot_judgment is not None
    assert parsed.bot_judgment.note == whatif._BOT_NOTE


def test_error_result_parses_as_whatif_response(monkeypatch):
    _patch_stock(monkeypatch, [], source=None)

    result = whatif.compute_whatif(_CODE, "2024-01-04", 1_000_000)

    parsed = WhatIfResponse(**result)
    assert parsed.error == "해당 날짜 이전 데이터 없음 — 상장 전이거나 조회 범위(약 4년) 밖"
    assert parsed.buy_price is None
    assert parsed.kospi is None
    assert parsed.bot_judgment is None


# ────────────────────────────────────────────
# 9. 회귀 — amount<=0 방어 (군관 발견 결함의 수정 후 계약 고정)
# ────────────────────────────────────────────
# 과거: _calc_side()의 return_pct = profit / amount * 100 이 amount=0 에서
# ZeroDivisionError 로 전파되는 결함이 있었음(군관 발견). compute_whatif 최상단에
# amount<=0 조기 반환 방어가 추가되어, 이제는 크래시 없이 error 응답을 돌려준다.

def test_zero_or_negative_amount_returns_error_without_crash(monkeypatch):
    """amount<=0 이면 크래시 대신 error 필드가 담긴 빈 응답을 돌려준다(방어 계약)."""
    items = [_item("2024-01-02", 100.0)]
    _patch_stock(monkeypatch, items)

    for bad_amount in (0, -1000):
        result = whatif.compute_whatif(_CODE, "2024-01-02", bad_amount)
        assert result["error"] is not None
        assert "1원 이상" in result["error"]
        assert result["eval_amount"] is None
        assert result["profit"] is None
