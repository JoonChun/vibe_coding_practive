"""시장 상태 라우트 — 장전/장중/장마감/휴장.

외부 API 를 부르지 않는 순수 계산이라 캐시도 스레드 오프로드도 필요 없다.
카운트다운("마감까지 N시간 M분")은 서버가 보낸 세션 경계로 프론트가 로컬 계산한다 —
초 단위 갱신을 위해 서버를 폴링할 이유가 없다.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

import market_calendar
from config import TIMEZONE

from ..schemas import MarketStatusResponse

router = APIRouter(prefix="/api")


@router.get("/market/status", response_model=MarketStatusResponse)
def get_market_status():
    now = datetime.now(ZoneInfo(TIMEZONE))
    return market_calendar.market_status(now)
