import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from config import (
    KIS_APPROVAL_URL,
    KIS_TOKEN_URL,
    KIS_APP_KEY_ENV,
    KIS_APP_SECRET_ENV,
    TIMEZONE,
)

_TOKEN_CACHE = {"access_token": None, "expires_at": None}
# 토큰/approval_key 발급 구간 보호용 락. 부팅·만료 직후 콜드미스 시 여러 스레드
# (candles 요청·kis_ws·collector·크론)가 동시에 발급 요청을 쏘면 KIS 발급 rate-limit
# (EGW00133)에 걸린다 → double-checked locking 으로 발급을 단일화한다.
_TOKEN_LOCK = threading.Lock()

# WebSocket 접속키(approval_key) 전용 캐시 — REST 접근토큰(get_token/_TOKEN_CACHE)과는
# 발급 절차·유효기간이 달라 별도 캐시로 분리한다(공식 유효기간 24시간, 여유를 두고 23시간
# 캐시). kis_ws.py(server/services)가 재연결 시마다 이 함수를 호출하므로 캐시가 필수.
_APPROVAL_KEY_CACHE = {"approval_key": None, "expires_at": None}
_APPROVAL_KEY_TTL_HOURS = 23
_APPROVAL_KEY_LOCK = threading.Lock()


def _load_cache() -> str | None:
    try:
        expires_at = _TOKEN_CACHE.get("expires_at")
        access_token = _TOKEN_CACHE.get("access_token")
        if expires_at is None or access_token is None:
            return None
        now = datetime.now(ZoneInfo(TIMEZONE))
        if now < expires_at:
            return access_token
    except Exception:
        pass
    return None


def _save_cache(token: str, expires_in: int) -> None:
    try:
        expires_at = datetime.now(ZoneInfo(TIMEZONE)) + timedelta(seconds=expires_in - 300)
        _TOKEN_CACHE["access_token"] = token
        _TOKEN_CACHE["expires_at"] = expires_at
    except Exception:
        pass


def _request_token(payload: dict) -> dict:
    max_attempts = 3
    backoff_seconds = [1, 2, 4]
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            resp = requests.post(KIS_TOKEN_URL, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_error = e
            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds[attempt])

    raise RuntimeError(f"토큰 발급 요청 실패: {last_error}") from last_error


def get_token() -> str:
    cached = _load_cache()
    if cached:
        return cached

    # 락 밖에서 1차 확인(위)해 hot-path 경합을 피하고, 콜드미스일 때만 락 진입.
    with _TOKEN_LOCK:
        # 락 대기 중 다른 스레드가 이미 발급했을 수 있으므로 재확인(double-checked).
        cached = _load_cache()
        if cached:
            return cached

        app_key = os.environ.get(KIS_APP_KEY_ENV)
        app_secret = os.environ.get(KIS_APP_SECRET_ENV)

        if not app_key or not app_secret:
            raise RuntimeError("KIS_APP_KEY 또는 KIS_APP_SECRET 환경변수가 없습니다.")

        payload = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "appsecret": app_secret,
        }

        data = _request_token(payload)
        token = data.get("access_token")
        if not token:
            raise RuntimeError(f"access_token 없음. 응답: {data}")

        expires_in = int(data.get("expires_in", 86400))
        _save_cache(token, expires_in)
        return token


# ────────────────────────────────────────────
# WebSocket 접속키(approval_key) — 국내주식 실시간체결가 등 KIS WS 구독에 필요.
# REST 접근토큰(get_token)과 발급 endpoint·요청 바디 키명이 다르다(appkey는 동일하나
# secret 파라미터명이 "secretkey" — REST 쪽 "appsecret"과 다름에 유의).
#
# 참고(공식 예제, WebFetch로 확인):
# github.com/koreainvestment/open-trading-api examples_llm/kis_auth.py 의 auth_ws() —
#   POST {url}/oauth2/Approval, body {"grant_type":"client_credentials","appkey":...,
#   "secretkey":...} → 응답 JSON의 "approval_key" 필드를 그대로 사용.
# ────────────────────────────────────────────

def _load_approval_key_cache() -> str | None:
    try:
        expires_at = _APPROVAL_KEY_CACHE.get("expires_at")
        approval_key = _APPROVAL_KEY_CACHE.get("approval_key")
        if expires_at is None or approval_key is None:
            return None
        now = datetime.now(ZoneInfo(TIMEZONE))
        if now < expires_at:
            return approval_key
    except Exception:
        pass
    return None


def _save_approval_key_cache(approval_key: str) -> None:
    try:
        expires_at = datetime.now(ZoneInfo(TIMEZONE)) + timedelta(hours=_APPROVAL_KEY_TTL_HOURS)
        _APPROVAL_KEY_CACHE["approval_key"] = approval_key
        _APPROVAL_KEY_CACHE["expires_at"] = expires_at
    except Exception:
        pass


def _request_approval(payload: dict) -> dict:
    max_attempts = 3
    backoff_seconds = [1, 2, 4]
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            resp = requests.post(KIS_APPROVAL_URL, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_error = e
            if attempt < max_attempts - 1:
                time.sleep(backoff_seconds[attempt])

    raise RuntimeError(f"approval_key 발급 요청 실패: {last_error}") from last_error


def get_approval_key() -> str:
    """KIS WebSocket 접속키(approval_key) 발급. in-memory 23시간 캐시.

    발급 실패(환경변수 없음·요청 실패·응답에 approval_key 없음) 시 RuntimeError.
    server/services/kis_ws.py 가 최초 연결·재연결마다 호출한다.
    """
    cached = _load_approval_key_cache()
    if cached:
        return cached

    with _APPROVAL_KEY_LOCK:
        # double-checked: 락 대기 중 다른 스레드가 이미 발급했을 수 있음.
        cached = _load_approval_key_cache()
        if cached:
            return cached

        app_key = os.environ.get(KIS_APP_KEY_ENV)
        app_secret = os.environ.get(KIS_APP_SECRET_ENV)

        if not app_key or not app_secret:
            raise RuntimeError("KIS_APP_KEY 또는 KIS_APP_SECRET 환경변수가 없습니다.")

        payload = {
            "grant_type": "client_credentials",
            "appkey": app_key,
            "secretkey": app_secret,
        }

        data = _request_approval(payload)
        approval_key = data.get("approval_key")
        if not approval_key:
            raise RuntimeError(f"approval_key 없음. 응답: {data}")

        _save_approval_key_cache(approval_key)
        return approval_key
