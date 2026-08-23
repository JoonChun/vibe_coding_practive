"""시장 폭(등락종목수) 파싱 + 지수 3단 폴백.

KIS 자격증명이 없어 실호출로 검증할 수 없다. 응답 픽스처는 공식 예제
chk_inquire_index_price.py 의 COLUMN_MAPPING 필드명을 그대로 사용해, 실환경에서
필드명이 어긋나 조용히 전부 None 이 되는 것을 막는 안전망 역할을 한다.

특히 잠그는 것:
  · 전일 대비 부호는 prdy_vrss_sign 으로만 결정한다(원문에 부호가 있어도 이중 반전 금지)
  · 상승·하락 둘 다 없으면 breadth=None — 0으로 채운 빈 바를 그리면
    "오늘 아무 종목도 안 움직였다"로 오해된다
  · 폴백 경로(일자별 지수·yfinance)에는 시장 폭이 없으므로 반드시 None
"""
from server.services import indices


def _index_output(**over) -> dict:
    """FHPUP02100000 output 픽스처 — 공식 COLUMN_MAPPING 필드명 그대로."""
    base = {
        "bstp_nmix_prpr": "2650.42",
        "bstp_nmix_prdy_vrss": "18.30",
        "prdy_vrss_sign": "2",       # 2 = 상승
        "bstp_nmix_prdy_ctrt": "0.70",
        "ascn_issu_cnt": "512",
        "stnr_issu_cnt": "78",
        "down_issu_cnt": "334",
        "uplm_issu_cnt": "3",
        "lslm_issu_cnt": "1",
    }
    base.update(over)
    return base


# ── 시장 폭 파싱 ──

def test_parse_breadth_reads_official_field_names():
    b = indices._parse_breadth(_index_output())

    assert b == {"up": 512, "flat": 78, "down": 334, "limit_up": 3, "limit_down": 1}


def test_parse_breadth_none_when_updown_missing():
    """상승·하락이 둘 다 없으면 의미 없는 부분데이터 → None (빈 바 방지)."""
    assert indices._parse_breadth({}) is None
    assert indices._parse_breadth({"stnr_issu_cnt": "10"}) is None


def test_parse_breadth_fills_missing_optional_counts_with_zero():
    b = indices._parse_breadth({"ascn_issu_cnt": "5", "down_issu_cnt": "3"})

    assert b == {"up": 5, "flat": 0, "down": 3, "limit_up": 0, "limit_down": 0}


def test_parse_breadth_ignores_unparsable_values():
    b = indices._parse_breadth(_index_output(uplm_issu_cnt="N/A"))
    assert b["limit_up"] == 0
    assert b["up"] == 512


# ── 부호 처리 ──

def _fetch_with(output, monkeypatch):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rt_cd": "0", "output": output}

    import kis_auth
    import requests

    monkeypatch.setattr(kis_auth, "get_token", lambda: "tok")
    monkeypatch.setattr(kis_auth, "kis_throttle", lambda: None)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())
    return indices._fetch_kis_index_price("0001")


def test_sign_polarity_rising(monkeypatch):
    value, change, pct, breadth = _fetch_with(_index_output(), monkeypatch)

    assert value == 2650.42
    assert change == 18.3
    assert pct == 0.7
    assert breadth["up"] == 512


def test_sign_polarity_falling_does_not_double_negate(monkeypatch):
    """원문에 이미 '-' 가 붙어 와도 부호 코드로만 극성을 정한다(이중 반전 금지)."""
    out = _index_output(
        prdy_vrss_sign="5",              # 5 = 하락
        bstp_nmix_prdy_vrss="-18.30",    # 원문에 부호 있음
        bstp_nmix_prdy_ctrt="-0.70",
    )
    _, change, pct, _ = _fetch_with(out, monkeypatch)

    assert change == -18.3
    assert pct == -0.7


def test_sign_polarity_flat(monkeypatch):
    out = _index_output(prdy_vrss_sign="3", bstp_nmix_prdy_vrss="0", bstp_nmix_prdy_ctrt="0")
    _, change, pct, _ = _fetch_with(out, monkeypatch)

    assert change == 0.0
    assert pct == 0.0


def test_limit_up_sign_code_treated_as_rising(monkeypatch):
    """1 = 상한가도 상승이다(kis_ws 와 동일 관례)."""
    _, change, _, _ = _fetch_with(_index_output(prdy_vrss_sign="1"), monkeypatch)
    assert change == 18.3


def test_output_as_list_is_tolerated(monkeypatch):
    """문서상 object 지만 배열 변형에 대비한 방어가 동작하는지."""
    value, _, _, breadth = _fetch_with([_index_output()], monkeypatch)
    assert value == 2650.42
    assert breadth is not None


def test_missing_index_value_raises_to_trigger_fallback(monkeypatch):
    import pytest

    with pytest.raises(RuntimeError):
        _fetch_with(_index_output(bstp_nmix_prpr="N/A"), monkeypatch)


def test_empty_output_raises_to_trigger_fallback(monkeypatch):
    import pytest

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"rt_cd": "1", "msg1": "권한없음", "output": None}

    import kis_auth
    import requests

    monkeypatch.setattr(kis_auth, "get_token", lambda: "tok")
    monkeypatch.setattr(kis_auth, "kis_throttle", lambda: None)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _Resp())

    with pytest.raises(RuntimeError):
        indices._fetch_kis_index_price("0001")


# ── 3단 폴백 ──

def test_fallback_to_daily_index_has_no_breadth(monkeypatch):
    """일자별 지수 경로에는 등락종목수가 없다 → breadth 는 반드시 None."""
    def boom(_iscd):
        raise RuntimeError("현재지수 실패")

    monkeypatch.setattr(indices, "_fetch_kis_index_price", boom)
    monkeypatch.setattr(indices, "_fetch_kis_index", lambda _iscd: (2600.0, 5.0, 0.19))

    value, change, pct, breadth, source = indices._fetch_one(indices._INDEX_DEFS[0])

    assert (value, change, pct) == (2600.0, 5.0, 0.19)
    assert breadth is None
    assert source == "kis"


def test_fallback_to_yfinance_has_no_breadth(monkeypatch):
    def boom(_x):
        raise RuntimeError("KIS 실패")

    monkeypatch.setattr(indices, "_fetch_kis_index_price", boom)
    monkeypatch.setattr(indices, "_fetch_kis_index", boom)
    monkeypatch.setattr(indices, "_fetch_yf_index", lambda _sym: (2590.0, -3.0, -0.12))

    value, change, pct, breadth, source = indices._fetch_one(indices._INDEX_DEFS[0])

    assert (value, change, pct) == (2590.0, -3.0, -0.12)
    assert breadth is None
    assert source == "yfinance"


def test_per_index_failure_is_isolated(monkeypatch):
    """한 지수 실패가 다른 지수를 막지 않는다."""
    monkeypatch.setattr(indices, "_cache", {})

    def selective(d):
        if d["code"] == "KOSPI":
            return 2650.0, 18.0, 0.7, {"up": 1, "flat": 0, "down": 0,
                                       "limit_up": 0, "limit_down": 0}, "kis"
        raise RuntimeError("코스닥 전부 실패")

    monkeypatch.setattr(indices, "_fetch_one", selective)

    by_code = {it["code"]: it for it in indices.get_indices()["items"]}

    assert by_code["KOSPI"]["error"] is None
    assert by_code["KOSPI"]["breadth"]["up"] == 1
    assert by_code["KOSDAQ"]["error"] is not None
    assert by_code["KOSDAQ"]["breadth"] is None
    # 실패 항목도 스키마가 동일해야 프론트가 균일하게 다룬다.
    assert set(by_code["KOSPI"]) == set(by_code["KOSDAQ"])
