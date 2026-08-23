"""Phase 3 "그날의 나" 타임머신(What-if) 서비스.

GET /api/stocks/{code}/whatif 라우트의 비즈니스 로직. 순수 계산 서비스 — 자체 스케줄러·
백그라운드 스레드 없음(collector.py/tick_aggregator.py 와 무관, 건드리지 않음).

흐름:
  1) 종목 일봉(candles.get_candles(code,"1d",1000) — 기존 read-through 그대로 재사용)에서
     요청 날짜(KST 자정 epoch) 이하 중 가장 늦은 봉을 "매수일"로 채택한다(휴장일 자동 보정 —
     주말·공휴일에 조회해도 직전 거래일 종가로 자연히 매수한 것처럼 계산됨).
  2) 그 매수일 이전 데이터가 아예 없으면(상장 전이거나 조회 범위 밖 — read-through 저장
     깊이가 대략 4년) error 필드를 채우고 나머지는 전부 null 인 200 응답을 돌려준다
     (candles 라우트의 "빈 items 도 200" 계약과 같은 스타일 — 데이터 없음은 예외가 아니다).
  3) 손익은 "단순 가격 기준"이다 — 배당·액면분할·매매수수료·세금은 전혀 반영하지 않는다.
     shares = amount / buy_close (소수 주식 허용 — 실제 매매 단위 제약 무시, 순수 비율 계산).
  4) 같은 매수일 기준으로 코스피 지수(candles.get_index_candles)를 병치 계산한다 — 지수
     데이터가 없어도(신규 상장 전 지수야 항상 있지만, fetch 실패 등 예외 상황 대비) kospi
     필드만 null 처리하고 나머지 응답은 정상적으로 채운다.
  5) "그날의 봇 판정"은 매수일까지의 데이터만 슬라이스해 macd_cross_signal/rsi_zone_signal/
     pullback_signal/long_term_view 에 그대로 투입한다(재무비율은 과거 시점 재현이 불가능해
     인자 None 고정 — long_term_view 가 None → 펀더멘털 점수 0으로 자동 처리하는 기존 로직
     그대로 재사용). indicators.py 각 함수는 데이터부족을 스스로 감지해 "데이터부족" 류
     문자열/None 을 돌려주므로 이 서비스에서 별도 부족 처리를 하지 않는다.

pandas 연산(지표 계산)이 섞여 있어 블로킹이다 — 호출부(라우터)에서 asyncio.to_thread 로
감싸야 한다(기존 candles 라우트와 동일 관례).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

import indicators
from config import TIMEZONE

from . import candles

logger = logging.getLogger(__name__)

_TZ = ZoneInfo(TIMEZONE)

_NO_DATA_ERROR = "해당 날짜 이전 데이터 없음 — 상장 전이거나 조회 범위(약 4년) 밖"
_BAD_PRICE_ERROR = "가격 데이터 불완전 — 계산 불가"
_BOT_NOTE = "가격 기반 지표만 — PER/PBR/ROE는 과거 재현 불가로 제외"


def _requested_epoch(date_str: str) -> int | None:
    """'YYYY-MM-DD' → KST 자정 기준 Unix epoch(초). candles.py의 _kst_midnight_epoch와
    동일한 기준(같은 날짜 문자열이면 항상 같은 epoch)이라 캔들 t 값과 직접 비교 가능하다."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=_TZ)
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _epoch_to_date_str(t: int) -> str:
    return datetime.fromtimestamp(t, tz=_TZ).strftime("%Y-%m-%d")


def _find_buy_index(items: list[dict], requested_epoch: int) -> int | None:
    """items(t 오름차순) 중 t<=requested_epoch 인 마지막(가장 늦은) 인덱스. 없으면 None."""
    buy_idx = None
    for idx, item in enumerate(items):
        t = item.get("t")
        if t is None:
            continue
        if t <= requested_epoch:
            buy_idx = idx
        else:
            break  # 오름차순이므로 한 번 초과하면 이후로도 계속 초과
    return buy_idx


def _empty_response(code: str, date_str: str, amount: int, source: str | None, error: str) -> dict:
    return {
        "code": code,
        "requested_date": date_str,
        "buy_date": None,
        "buy_price": None,
        "amount": amount,
        "shares": None,
        "current_date": None,
        "current_price": None,
        "eval_amount": None,
        "profit": None,
        "return_pct": None,
        "multiple": None,
        "kospi": None,
        "bot_judgment": None,
        "source": source,
        "error": error,
    }


def _calc_side(buy_price, current_price, amount: int) -> dict | None:
    """가격 비율 기준 손익 계산 공통 로직(종목·코스피 병치 모두 재사용). 가격이 없거나
    매수가가 0이면 계산 불가(None)."""
    if buy_price is None or current_price is None or not buy_price:
        return None
    eval_amount = (amount / buy_price) * current_price
    profit = eval_amount - amount
    return_pct = profit / amount * 100
    multiple = eval_amount / amount
    return {
        "buy_price": round(float(buy_price), 2),
        "current_price": round(float(current_price), 2),
        "eval_amount": round(eval_amount),
        "profit": round(profit),
        "return_pct": round(return_pct, 2),
        "multiple": round(multiple, 1),
    }


def _items_to_df(items: list[dict]) -> pd.DataFrame:
    return pd.DataFrame({
        "open": [i.get("open") for i in items],
        "high": [i.get("high") for i in items],
        "low": [i.get("low") for i in items],
        "close": [i.get("close") for i in items],
        "volume": [i.get("volume") for i in items],
    })


def _compute_bot_judgment(stock_items: list[dict], buy_idx: int) -> dict:
    """매수일(buy_idx)까지의 슬라이스만으로 그 시점 기준 봇 판정을 재현한다."""
    slice_items = stock_items[: buy_idx + 1]
    df = _items_to_df(slice_items)

    try:
        macd_1d = indicators.macd_cross_signal(df)
        rsi_1d = indicators.rsi_zone_signal(df)
        pullback = indicators.pullback_signal(df)
        long_view = indicators.long_term_view(macd_1d, rsi_1d, None, None, None)
    except Exception as e:
        # indicators.py 각 함수는 데이터부족을 스스로 "데이터부족"/None 으로 처리해 통상
        # 예외를 던지지 않는다 — 그래도 예기치 못한 입력(전량 NaN 등)에 whatif 응답
        # 전체가 500 으로 죽는 것만은 막는다(기존 crawler.py _fetch_from_kis 의
        # 지표 계산 실패 격리 관례와 동일).
        logger.warning(f"[whatif] 봇 판정 계산 실패: {e}")
        macd_1d = None
        rsi_1d = None
        pullback = {"status": None}
        long_view = "데이터부족"

    return {
        "long_view": long_view,
        "macd_1d": macd_1d,
        "rsi_1d": rsi_1d,
        "pullback_status": pullback.get("status"),
        "note": _BOT_NOTE,
    }


def compute_whatif(code: str, date_str: str, amount: int) -> dict:
    """그날의 나 What-if 손익·봇 판정 계산. 순수 계산 함수(pandas 연산 포함 — 블로킹).

    code 는 호출부에서 이미 db.normalize_code 로 정규화되어 있다고 가정(라우터 계약).
    date_str 형식(YYYY-MM-DD)·미래 날짜 검증도 라우터에서 선행한다 — 이 함수는 그 검증을
    통과한 입력을 받는다는 전제지만, 방어적으로 파싱 실패도 처리한다.
    """
    # 라우터가 amount ge=1 을 선행 검증하지만, 서비스 직접 호출 대비 방어
    # (amount=0 이면 _calc_side 의 return_pct 분모가 0 — ZeroDivisionError, 군관 발견).
    if amount <= 0:
        return _empty_response(code, date_str, amount, None, "금액은 1원 이상이어야 합니다")

    requested_epoch = _requested_epoch(date_str)
    if requested_epoch is None:
        return _empty_response(code, date_str, amount, None, f"날짜 형식 오류(YYYY-MM-DD): {date_str}")

    stock_result = candles.get_candles(code, "1d", 1000)
    stock_items = stock_result.get("items") or []
    stock_source = stock_result.get("source")

    buy_idx = _find_buy_index(stock_items, requested_epoch)
    if buy_idx is None:
        return _empty_response(code, date_str, amount, stock_source, _NO_DATA_ERROR)

    buy_item = stock_items[buy_idx]
    latest_item = stock_items[-1]
    buy_price = buy_item.get("close")
    current_price = latest_item.get("close")

    side = _calc_side(buy_price, current_price, amount)
    if side is None:
        return _empty_response(code, date_str, amount, stock_source, _BAD_PRICE_ERROR)

    buy_date = _epoch_to_date_str(buy_item["t"])
    current_date = _epoch_to_date_str(latest_item["t"])
    shares = round(amount / buy_price, 4)

    # 코스피 지수 병치 — 실패해도 전체 응답을 막지 않고 kospi=null 로 처리.
    kospi_block = None
    try:
        index_items = candles.get_index_candles(1000)
    except Exception as e:
        logger.warning(f"[whatif] 코스피 지수 조회 실패({code}, {date_str}): {e}")
        index_items = []

    if index_items:
        idx_buy_idx = _find_buy_index(index_items, requested_epoch)
        if idx_buy_idx is not None:
            idx_buy_item = index_items[idx_buy_idx]
            idx_latest_item = index_items[-1]
            kospi_block = _calc_side(
                idx_buy_item.get("close"), idx_latest_item.get("close"), amount
            )

    bot_judgment = _compute_bot_judgment(stock_items, buy_idx)

    return {
        "code": code,
        "requested_date": date_str,
        "buy_date": buy_date,
        "buy_price": side["buy_price"],
        "amount": amount,
        "shares": shares,
        "current_date": current_date,
        "current_price": side["current_price"],
        "eval_amount": side["eval_amount"],
        "profit": side["profit"],
        "return_pct": side["return_pct"],
        "multiple": side["multiple"],
        "kospi": kospi_block,
        "bot_judgment": bot_judgment,
        "source": stock_source,
        "error": None,
    }
