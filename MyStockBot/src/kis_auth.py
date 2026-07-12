import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from config import KIS_TOKEN_URL, KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV, TIMEZONE

_TOKEN_CACHE = {"access_token": None, "expires_at": None}


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
