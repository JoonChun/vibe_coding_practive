"""스냅샷 응답의 판정 근거 계약 — 화면이 점수를 재계산하지 않아도 되는지 검증.

예전 구조에서는 프론트(web/src/utils/factorScoring.ts)가 점수표·임계값·설명문을 TS 로
복제해 스스로 계산했고, 그 파일 주석이 "백엔드 점수와 불일치할 수 있으므로 화면은 프론트
합계를 우선한다"고 명시하고 있었다. 즉 화면에 보이는 근거 합계와 실제 판정 점수가 갈라질 수
있었다. 여기서 "분해 합계 == 백엔드 판정 점수" 불변식을 고정한다.
"""
import indicators
from server.services import snapshot_cache

_ITEM = {
    "code": "005930", "name": "삼성전자",
    "close": 71000, "change": 1500, "change_pct": 2.16,
    "macd_1d": "골든크로스(진입)", "rsi_1d": "중립", "rsi_value_1d": 52.4,
    "macd_60m": "매도구간", "rsi_60m": "과매도(진입)", "rsi_value_60m": 28.3,
    "bb_upper": 73000, "bb_mid": 70000, "bb_lower": 67000,
    "per": 8.2, "pbr": 0.63, "roe": 18.1, "revenue": 1, "net_income": 1,
    "short_view": "관망", "long_view": "강력매수",
    "short_score": 0, "long_score": 5,
    "source": "kis", "source_60m": "yfinance", "error": None,
}


def _factors(item: dict) -> dict:
    out = snapshot_cache._to_snapshot_item(item)
    return out["factors"]


def test_breakdown_sum_equals_backend_score():
    """핵심 불변식 — 화면이 그리는 기여요인 합계가 판정에 쓰인 점수와 같아야 한다."""
    factors = _factors(_ITEM)

    assert sum(r["score"] for r in factors["breakdown_long"]) == factors["long_score"]
    assert sum(r["score"] for r in factors["breakdown_short"]) == factors["short_score"]


def test_breakdown_shapes():
    factors = _factors(_ITEM)

    # 단기 = MACD·RSI 2행 / 장기 = + PER·PBR·ROE 5행
    assert [r["key"] for r in factors["breakdown_short"]] == ["macd", "rsi"]
    assert [r["key"] for r in factors["breakdown_long"]] == [
        "macd", "rsi", "per", "pbr", "roe"
    ]
    for row in factors["breakdown_long"]:
        assert set(row) == {"key", "label", "score", "max_abs", "rule"}
        assert row["max_abs"] >= 1
        assert abs(row["score"]) <= row["max_abs"]
        assert row["rule"]  # 설명문이 비어 있으면 화면이 빈 줄을 그린다


def test_breakdown_labels_include_values():
    factors = _factors(_ITEM)
    by_key = {r["key"]: r for r in factors["breakdown_long"]}

    assert by_key["macd"]["label"] == "MACD 골든크로스(진입)"
    assert by_key["rsi"]["label"] == "RSI 중립 · RSI 52.4"
    assert by_key["per"]["label"] == "PER 8.2배"
    assert by_key["pbr"]["label"] == "PBR 0.63배"
    assert by_key["roe"]["label"] == "ROE 18.1%"


def test_missing_numbers_render_as_no_data_not_crash():
    item = {**_ITEM, "per": None, "pbr": None, "roe": None, "rsi_value_1d": None}
    factors = _factors(item)
    by_key = {r["key"]: r for r in factors["breakdown_long"]}

    assert by_key["per"]["label"] == "PER 데이터부족"
    assert by_key["per"]["score"] == 0
    # RSI 수치가 없으면 존 라벨만 남고 " · RSI xx.x" 꼬리가 붙지 않는다.
    assert by_key["rsi"]["label"] == "RSI 중립"


def test_failed_item_has_no_factors():
    """수집 실패 항목은 factors 가 None — 분해도 없어야 한다(화면은 빈 카드 처리)."""
    item = {**_ITEM, "error": "일봉 수집 실패"}
    assert snapshot_cache._to_snapshot_item(item)["factors"] is None


def test_rules_meta_matches_indicators():
    """응답의 rules 는 판정 엔진의 실제 임계값과 같아야 한다(프론트 하드코딩 제거의 근거)."""
    assert snapshot_cache._rules_meta() == indicators.decision_thresholds()
    meta = snapshot_cache._rules_meta()
    assert meta["weak"] == 1
    assert meta["short_strong"] == 2
    assert meta["long_strong"] == 3
    assert meta["long_strong_requires_tech_confirm"] is True


def test_breakdown_sum_consistency_across_factor_combinations():
    """여러 팩터 조합에서 불변식이 유지되는지 — 한 케이스만 맞는 우연을 배제."""
    cases = [
        {"macd_1d": "데드크로스(매도)", "rsi_1d": "과매수(매도)", "per": 40.0, "pbr": 5.0, "roe": -3.0},
        {"macd_1d": "진입구간", "rsi_1d": "중립", "per": 15.0, "pbr": 1.5, "roe": 5.0},
        {"macd_1d": "매도구간", "rsi_1d": "과매도(진입)", "per": 8.0, "pbr": 0.5, "roe": 20.0},
        {"macd_1d": None, "rsi_1d": None, "per": 8.0, "pbr": 0.5, "roe": 20.0},
    ]
    for patch in cases:
        item = {**_ITEM, **patch}
        # 판정 점수를 실제 엔진으로 다시 계산해 항목에 반영(collector 가 하는 일과 동일).
        item["long_score"] = indicators.long_term_score(
            item["macd_1d"], item["rsi_1d"], item["per"], item["pbr"], item["roe"]
        )
        factors = _factors(item)
        assert sum(r["score"] for r in factors["breakdown_long"]) == factors["long_score"], patch


# ────────────────────────────────────────────
# bars_60m — 단기 판정 워밍업 구간 표시용 (additive)
# ────────────────────────────────────────────
#
# 60분봉이 MACD 최소 봉수(35)에 못 미치면 지표는 '데이터부족'이 아니라 0점=관망을
# 낸다(RSI 는 15봉이면 '중립'을 내므로 합계가 0). 화면은 그 구간을 '축적 중'으로
# 구분해야 하는데, 그러려면 실제 봉 수가 응답에 실려야 한다.

def test_bars_60m_passthrough_to_factors():
    item = {**_ITEM, "bars_60m": 12}
    assert _factors(item)["bars_60m"] == 12


def test_bars_60m_absent_is_none_not_crash():
    """구버전 상태(키 없음)에서도 깨지지 않고 None 으로 내려간다."""
    item = {k: v for k, v in _ITEM.items() if k != "bars_60m"}
    assert _factors(item)["bars_60m"] is None


def test_failed_item_still_has_no_factors_with_bars():
    """수집 실패 항목은 bars_60m 유무와 무관하게 factors=None 계약 유지."""
    item = {**_ITEM, "bars_60m": 5, "error": "수집 실패"}
    assert snapshot_cache._to_snapshot_item(item)["factors"] is None
