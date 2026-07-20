import pytest

import db
import indicators


def test_normalize_code_ok():
    assert db.normalize_code("5930") == "005930"
    assert db.normalize_code(" 005930 ") == "005930"


def test_normalize_code_bad():
    for bad in ["", "notnum", "1234567"]:
        with pytest.raises(ValueError):
            db.normalize_code(bad)


def test_long_term_view_levels():
    # 5단계 라벨 중 하나를 돌려주고, 매수/매도 방향이 일관돼야 한다.
    buy = indicators.long_term_view("골든크로스(진입)", "과매도(진입)", 5, 0.5, 20)
    sell = indicators.long_term_view("데드크로스(매도)", "과매수(매도)", 50, 5, -5)
    levels = {"강력매수", "매수", "관망", "매도", "강력매도"}
    assert buy in levels and sell in levels
    assert buy in {"매수", "강력매수"}
    assert sell in {"매도", "강력매도"}
