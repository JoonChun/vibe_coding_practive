import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
from config import KIS_TOKEN_URL, KIS_APP_KEY_ENV, KIS_APP_SECRET_ENV, TIMEZONE

_CACHE_FILE = Path("/tmp/kis_token_cache.json")


def _load_cache() -> str | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        data = json.loads(_CACHE_FILE.read_text())
        expires_at = datetime.fromisoformat(data["expires_at"])
        now = datetime.now(ZoneInfo(TIMEZONE))
        if now < expires_at:
            return data["access_token"]
    except Exception:
        pass
    return None


def _save_cache(token: str, expires_in: int) -> None:
    try:
        from datetime import timedelta
        expires_at = datetime.now(ZoneInfo(TIMEZONE)) + timedelta(seconds=expires_in - 300)
        _CACHE_FILE.write_text(json.dumps({
            "access_token": token,
            "expires_at": expires_at.isoformat(),
        }))
    except Exception:
        pass


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

    try:
        resp = requests.post(KIS_TOKEN_URL, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"토큰 발급 요청 실패: {e}") from e

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError(f"access_token 없음. 응답: {data}")

    expires_in = int(data.get("expires_in", 86400))
    _save_cache(token, expires_in)
    return token
