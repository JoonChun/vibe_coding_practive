"""모의투자(Paper Trading) 서비스 — 시세 조립 + 평가손익 계산.

체결 가격은 collector 스냅샷(get_state)의 최신 종가를 사용한다(별도 시세 조회 없이
이미 수집 중인 관심종목 시세 재사용). 따라서 현재 시세가 수집된 종목(관심종목)만
거래 가능하다 — 시세가 없으면 PriceUnavailableError.

DB 계층(db.execute_paper_order 등)이 원자적 트랜잭션으로 잔액/보유를 보증하고,
여기서는 현재가로 보유 평가금액·손익을 덧입혀 응답을 만든다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import db
import market_calendar
from config import PAPER_SEED_DEFAULT, TIMEZONE

from . import collector


class PriceUnavailableError(Exception):
    """현재 시세가 수집되지 않은 종목으로 주문한 경우."""


def _price_map() -> dict[str, dict]:
    """collector 상태에서 code → {price, name} 매핑 구성(수집 실패 종목 제외)."""
    m: dict[str, dict] = {}
    state = collector.get_state()
    if state:
        for it in state.get("items", []):
            if it.get("error") is None and it.get("close") is not None:
                m[it["code"]] = {"price": it["close"], "name": it.get("name")}
    return m


def _enrich(account: dict, pmap: dict[str, dict]) -> dict:
    holdings = []
    holdings_value = 0.0
    priced_incomplete = False
    for h in account["holdings"]:
        price = pmap.get(h["code"], {}).get("price")
        cost = h["avg_cost"] * h["qty"]
        if price is not None:
            eval_amount = round(price * h["qty"], 2)
            pnl = round(eval_amount - cost, 2)
            pnl_pct = round((eval_amount - cost) / cost * 100, 2) if cost > 0 else None
            holdings_value += eval_amount
        else:
            # 현재가 부재(부팅 직후·수집 실패·관심종목 해제·상폐 등): 장부가(원가)로 평가한다.
            # 그래야 total_value/total_pnl 이 "seed 전액 손실"처럼 오표시되지 않는다. 개별
            # 손익은 미확정으로 두고 priced_incomplete 로 알린다.
            eval_amount = round(cost, 2)
            pnl = None
            pnl_pct = None
            holdings_value += eval_amount
            priced_incomplete = True
        holdings.append({
            **h,
            "price": price,
            "eval_amount": eval_amount,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
        })

    cash = account["cash"]
    seed = account["seed"]
    total_value = cash + holdings_value
    total_pnl = round(total_value - seed, 2)
    total_pnl_pct = round((total_value - seed) / seed * 100, 2) if seed > 0 else 0.0

    # 미실현손익 = 보유 평가금액 - 보유 원가. 실현손익은 DB가 거래에서 누적한 값이다.
    #
    # 수수료·세금이 없는 이 시뮬레이션에서는 두 값의 합이 총손익과 **정확히 일치한다**:
    #   realized   = Σ매도금액 - Σ(매도시 평균단가 × 수량)
    #   unrealized = 평가금액 - 보유원가 = 평가금액 - Σ매수금액 + Σ(매도시 평균단가 × 수량)
    #   합         = Σ매도 - Σ매수 + 평가금액 = (cash - seed) + 평가금액 = total_pnl
    # 이 항등식을 테스트로 잠근다 — 깨지면 어느 쪽 계산이 틀렸다는 신호다.
    # 단, 현재가가 없어 장부가로 평가한 보유가 있으면 그 종목의 미실현은 0으로 잡힌다
    # (priced_incomplete 가 그 사실을 알린다).
    holdings_cost = sum(h["avg_cost"] * h["qty"] for h in account["holdings"])
    unrealized_pnl = round(holdings_value - holdings_cost, 2)

    return {
        "cash": round(cash, 2),
        "seed": round(seed, 2),
        "holdings_value": round(holdings_value, 2),
        "total_value": round(total_value, 2),
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "realized_pnl": account["realized_pnl"],
        "unrealized_pnl": unrealized_pnl,
        # 마이그레이션 이전 매도(realized_pnl 미기록)가 남아 있으면 실현/미실현 분해가
        # 총손익과 맞지 않는다. 숫자를 억지로 맞추지 않고 그 사실을 노출한다.
        "realized_unknown_trades": account["realized_unknown_trades"],
        "priced_incomplete": priced_incomplete,
        "holdings": holdings,
    }


def get_account() -> dict:
    return _enrich(db.get_paper_account(PAPER_SEED_DEFAULT), _price_map())


def get_trades(limit: int = 100) -> dict:
    return {"items": db.get_paper_trades(limit)}


def place_order(code: str, side: str, qty: int) -> dict:
    norm = db.normalize_code(code)  # 형식 오류 시 ValueError
    pmap = _price_map()
    info = pmap.get(norm)
    price = info.get("price") if info else None
    name = (info.get("name") if info else None) or norm
    price_source = "market" if price is not None else None

    if price is None:
        # 시세 부재 시: 매도는 청산이 막히지 않도록 장부가(평균단가)로 체결을 허용하고
        # (상폐·거래정지·관심종목 해제로 시세 수집이 끊긴 보유의 영구 고착 방지),
        # 매수는 체결가를 알 수 없으므로 거부한다.
        if side == "sell":
            acct = db.get_paper_account(PAPER_SEED_DEFAULT)
            held = next((h for h in acct["holdings"] if h["code"] == norm), None)
            if held and held["qty"] > 0:
                price = float(held["avg_cost"])
                name = held.get("name") or name
                # 시장가가 아니라 장부가로 체결했다는 사실을 기록에 남긴다. 이걸 빼면
                # "그 가격에 팔렸다"가 사실이 아닌 거래 기록이 남고, 실현손익도 항상
                # 0이 되어(체결가 == 평균단가) 성적을 왜곡한다.
                price_source = "book"
        if price is None:
            raise PriceUnavailableError(
                f"현재 시세가 없어 매수할 수 없습니다({norm}). 관심종목에 추가해 "
                f"시세가 수집된 종목만 매수할 수 있습니다."
            )

    # 체결 시점의 장 상태를 함께 남긴다 — 장외 체결은 현실에서 불가능하므로 성적을
    # 볼 때 걸러낼 수 있어야 한다. market_calendar.market_status 는 외부 조회 없는
    # 순수 계산이라 체결 경로에서 불러도 안전하다.
    market_status = market_calendar.market_status(
        datetime.now(ZoneInfo(TIMEZONE))
    )["status"]

    account = db.execute_paper_order(
        norm, name, side, int(qty), float(price), PAPER_SEED_DEFAULT,
        price_source=price_source, market_status=market_status,
    )
    return _enrich(account, pmap)


def reset() -> dict:
    return _enrich(db.reset_paper_account(PAPER_SEED_DEFAULT), _price_map())
