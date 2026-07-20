"""모의투자(Paper Trading) 서비스 — 시세 조립 + 평가손익 계산.

체결 가격은 collector 스냅샷(get_state)의 최신 종가를 사용한다(별도 시세 조회 없이
이미 수집 중인 관심종목 시세 재사용). 따라서 현재 시세가 수집된 종목(관심종목)만
거래 가능하다 — 시세가 없으면 PriceUnavailableError.

DB 계층(db.execute_paper_order 등)이 원자적 트랜잭션으로 잔액/보유를 보증하고,
여기서는 현재가로 보유 평가금액·손익을 덧입혀 응답을 만든다.
"""
import db
from config import PAPER_SEED_DEFAULT

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
    return {
        "cash": round(cash, 2),
        "seed": round(seed, 2),
        "holdings_value": round(holdings_value, 2),
        "total_value": round(total_value, 2),
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
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
        if price is None:
            raise PriceUnavailableError(
                f"현재 시세가 없어 매수할 수 없습니다({norm}). 관심종목에 추가해 "
                f"시세가 수집된 종목만 매수할 수 있습니다."
            )

    account = db.execute_paper_order(
        norm, name, side, int(qty), float(price), PAPER_SEED_DEFAULT
    )
    return _enrich(account, pmap)


def reset() -> dict:
    return _enrich(db.reset_paper_account(PAPER_SEED_DEFAULT), _price_map())
