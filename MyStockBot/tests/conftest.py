"""pytest 전역 설정 — 이 레포 최초의 pytest 스위트.

server/main.py 와 동일한 sys.path 관례(MyStockBot 루트 + src/ 를 sys.path 에 추가)를
그대로 따른다 — server/services/*.py 가 `import db`, `import indicators`, `from config
import ...` 처럼 최상위 모듈 이름으로 import 하기 때문에, 이 관례를 깨면
`server.services.tick_aggregator` 자체를 import 할 수 없다.

서버(uvicorn)는 절대 기동하지 않는다 — 모듈 import 만으로 테스트 대상 함수에 접근한다.
"""
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))
