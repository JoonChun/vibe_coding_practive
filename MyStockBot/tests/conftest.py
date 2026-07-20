"""pytest 부트스트랩 — src/ 와 저장소 루트를 import 경로에 추가.

server 패키지는 루트 기준 `server.services.*` 로, 개별 모듈(db·indicators)은 src 기준으로 임포트한다.
"""
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
for _p in (_BASE, _BASE / "src"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)
