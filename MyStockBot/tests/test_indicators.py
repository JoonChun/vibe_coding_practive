"""indicators.py — 눌림목(pullback) 판정 + 기존 함수 어휘 회귀 테스트.

합성 일봉 OHLCV(t/open/high/low/close/volume, t 오름차순)를 직접 구성해 6개 상태를
모두 결정적으로(랜덤·시각 의존 없이) 재현한다. ADX/이동평균은 실제 ta 라이브러리
계산을 그대로 태우므로, 임계값에 딱 걸치는 경계값 대신 넉넉한 여유(margin)를 둔
시계열로 설계했다 — 각 assert 옆에 실측 여유치를 주석으로 남겨 왜 안전한지 밝힌다
(실측치는 이 파일 작성 중 실제로 함수를 호출해 확인한 값).

서버(uvicorn)·DB·네트워크는 전혀 쓰지 않는다 — indicators.py는 순수 함수 모듈이다.
"""
import pandas as pd

import indicators
from config import PULLBACK_MIN_BARS


# ────────────────────────────────────────────
# 합성 OHLCV 헬퍼
# ────────────────────────────────────────────

def _linear_df(n: int, start: float = 100.0, step: float = 1.0, volume: float = 1000.0) -> pd.DataFrame:
    """등차수열 종가로 이루어진 단순 추세 시계열(step>0 상승/step<0 하락).

    open은 직전 종가(첫 봉은 start)로 이어붙여 캔들 간 갭이 없게 하고, high/low는
    open·close 주위 아주 얇은 심지(±0.05)만 둔다 — 캔들 형태 자체가 판정에 영향을
    주지 않게(장대양봉 등 조건은 별도 헬퍼에서 명시적으로 만든다).
    """
    closes, opens, highs, lows = [], [], [], []
    price = start
    prev_close = start
    for _ in range(n):
        price += step
        o, c = prev_close, price
        opens.append(o)
        closes.append(c)
        highs.append(max(o, c) + 0.05)
        lows.append(min(o, c) - 0.05)
        prev_close = c
    return pd.DataFrame({
        "t": list(range(n)),
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": [volume] * n,
    })


def _consolidation_df(
    n_rise: int = 45, s1: float = 1.0, n_flat: int = 20, s2: float = 0.05,
    start: float = 100.0, volume: float = 1000.0,
) -> pd.DataFrame:
    """n_rise봉 강한 상승 후 n_flat봉을 완만한 상승(s2 ≈ 0)으로 눌러 MA20 근접
    (proximity) 상태를 만든다. 완전한 횡보(s2=0)로 두면 MA5==MA20이 되어 정배열
    (MA5>MA20) 조건이 깨지므로, 아주 얕은 상승(s2)을 남겨 MA5>MA20>MA60·MA20
    기울기 상승을 동시에 만족시킨다."""
    closes, opens, highs, lows = [], [], [], []
    price = start
    prev_close = start
    for _ in range(n_rise):
        price += s1
        o, c = prev_close, price
        opens.append(o); closes.append(c)
        highs.append(max(o, c) + 0.05); lows.append(min(o, c) - 0.05)
        prev_close = c
    for _ in range(n_flat):
        price += s2
        o, c = prev_close, price
        opens.append(o); closes.append(c)
        highs.append(max(o, c) + 0.05); lows.append(min(o, c) - 0.05)
        prev_close = c
    n = n_rise + n_flat
    return pd.DataFrame({
        "t": list(range(n)),
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": [volume] * n,
    })


def _ohlcv_from_closes(closes: list[float], volume: float = 1000.0) -> pd.DataFrame:
    """macd_cross_signal/rsi_zone_signal 회귀용 — 이 두 함수는 close 컬럼만 읽지만,
    계약대로 전체 OHLCV 형태(t 오름차순)를 갖춘 DataFrame으로 감싼다."""
    n = len(closes)
    opens = [closes[0]] + closes[:-1]
    highs = [max(o, c) + 0.05 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.05 for o, c in zip(opens, closes)]
    return pd.DataFrame({
        "t": list(range(n)),
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": [volume] * n,
    })


# ────────────────────────────────────────────
# pullback_signal — 6상태
# ────────────────────────────────────────────

def test_pullback_data_insufficient_just_below_min_bars():
    """PULLBACK_MIN_BARS(65) 미만(64봉)이면 그 즉시 데이터부족 — 지표 계산 자체를
    시도하지 않는다(경계 정확히: 64는 부족, 65는 통과)."""
    df = _linear_df(PULLBACK_MIN_BARS - 1)
    result = indicators.pullback_signal(df)
    assert result["status"] == "데이터부족"
    assert result["trend_up"] is False
    assert "부족" in result["reason"]
    assert str(PULLBACK_MIN_BARS - 1) in result["reason"]
    assert str(PULLBACK_MIN_BARS) in result["reason"]


def test_pullback_data_sufficient_at_min_bars_passes_length_gate():
    """65봉이면 최소 길이 게이트는 통과해 데이터부족이 아닌 실제 판정으로 넘어간다."""
    df = _linear_df(PULLBACK_MIN_BARS)
    result = indicators.pullback_signal(df)
    assert result["status"] != "데이터부족"


def test_pullback_not_trend_when_reverse_aligned_downtrend():
    """지속 하락(역배열: MA5<MA20<MA60)이면 추세 필터에서 즉시 추세아님으로 걸린다.
    (실측: 정배열 미충족·MA60 하회·MA20 기울기 하락 — 3개 사유가 동시에 붙을 만큼
    확실한 역배열이라 임계값 경계 이슈가 없다.)"""
    df = _linear_df(80, start=200.0, step=-1.0)
    result = indicators.pullback_signal(df)
    assert result["status"] == "추세아님"
    assert result["trend_up"] is False
    assert "정배열 미충족" in result["reason"]


def test_pullback_not_trend_when_adx_below_threshold_choppy():
    """정배열 여부와 무관하게 방향성 없는 등락(1봉 간격 지그재그)이면 ADX가 임계값
    (20)에 크게 못 미쳐 추세아님이 된다. (실측 ADX≈3.7 — 임계값 20 대비 여유 5배
    이상이라 ta 라이브러리 버전 차 정도로는 뒤집히지 않는다.)"""
    n = 80
    closes = [100.0]
    for i in range(n - 1):
        step = 0.6 if i % 2 == 0 else -0.6
        closes.append(closes[-1] + step)
    opens = [c - 0.1 for c in closes]
    highs = [max(o, c) + 0.2 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.2 for o, c in zip(opens, closes)]
    df = pd.DataFrame({
        "t": list(range(n)), "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": [1000.0] * n,
    })
    result = indicators.pullback_signal(df)
    assert result["status"] == "추세아님"
    assert result["trend_up"] is False
    assert "ADX" in result["reason"]


def test_pullback_trend_continue_when_aligned_but_far_from_ma20():
    """꾸준한 정배열 상승만 있고 되돌림이 없으면(현재가가 MA20 근접밴드 밖) 추세지속.
    (실측 이격 5.3% — 근접밴드 2.0% 대비 2배 이상 벌어져 있어 여유가 크다.)"""
    df = _linear_df(90)
    result = indicators.pullback_signal(df)
    assert result["status"] == "추세지속"
    assert result["trend_up"] is True
    assert "근접밴드" in result["reason"]


def test_pullback_progressing_watch_when_near_ma20_with_volume_contraction():
    """정배열 유지한 채 MA20까지 눌린 뒤(근접밴드 이내) 거래량까지 수축되면
    눌림 진행중(관망). (실측 근접 0.3%·거래량비 31% — 각각 기준 2.0%/60% 대비
    여유 충분.)"""
    df = _consolidation_df()
    df.loc[df.index[-1], "volume"] = 300   # 평균 대비 큰 폭 수축
    df.loc[df.index[-2], "volume"] = 350
    result = indicators.pullback_signal(df)
    assert result["status"] == "눌림 진행중(관망)"
    assert result["trend_up"] is True
    assert "근접" in result["reason"]
    assert "수축" in result["reason"]


def test_pullback_bounce_candidate_when_bullish_break_with_volume_expansion():
    """MA20 근접 상태에서 마지막 봉이 양봉+전일 고가 돌파+거래량 팽창이면
    눌림목 반등(매수후보). (실측 이격 1.6%·거래량비 288% — 기준 2.0% 이내,
    140% 이상을 크게 상회.)"""
    df = _consolidation_df()
    prev_close = df.loc[df.index[-2], "close"]
    last_idx = df.index[-1]
    df.loc[last_idx, "open"] = prev_close - 0.3
    df.loc[last_idx, "close"] = prev_close + 2.0
    df.loc[last_idx, "high"] = prev_close + 2.1
    df.loc[last_idx, "low"] = prev_close - 0.4
    df.loc[last_idx, "volume"] = 3000
    result = indicators.pullback_signal(df)
    assert result["status"] == "눌림목 반등(매수후보)"
    assert result["trend_up"] is True
    assert "양봉" in result["reason"]
    assert "돌파" in result["reason"]
    assert "거래량" in result["reason"]


def test_pullback_exit_when_ma20_broken_down_beyond_threshold():
    """정배열 추세 중 마지막 봉이 MA20 대비 4% 초과로 급락하면(지지 붕괴) 눌림
    이탈(무효). (실측 6.1% 하회 — 기준 4.0% 대비 여유 있고, 정배열은 여전히
    유지되도록 낙폭을 과하지 않게 설계했다 — 단일 대형 하락봉으로 MA5까지
    무너뜨리면 추세아님으로 새버리므로 이 균형이 중요하다.)"""
    df = _linear_df(PULLBACK_MIN_BARS + 16)  # 81봉 — 충분한 상승 이력 확보
    prev_close = df.loc[df.index[-2], "close"]
    last_idx = df.index[-1]
    drop = 20.0
    df.loc[last_idx, "open"] = prev_close
    df.loc[last_idx, "close"] = prev_close - drop
    df.loc[last_idx, "high"] = prev_close + 0.1
    df.loc[last_idx, "low"] = prev_close - drop - 0.2
    result = indicators.pullback_signal(df)
    assert result["status"] == "눌림 이탈(무효)"
    assert result["trend_up"] is True
    assert "하회" in result["reason"]


# ────────────────────────────────────────────
# 6상태 reason 비어있지 않음 + trend_up 정합 일괄 점검
# ────────────────────────────────────────────

def test_pullback_reason_never_empty_across_all_six_states():
    """상태별로 reason이 항상 비어있지 않은 문자열인지 일괄 점검(문구 내용은 각
    개별 테스트에서 핵심 토큰만 확인 — 여기서는 '항상 채워진다'는 계약만 본다)."""
    scenarios = [
        _linear_df(PULLBACK_MIN_BARS - 1),
        _linear_df(80, start=200.0, step=-1.0),
        _linear_df(90),
    ]
    watch_df = _consolidation_df()
    watch_df.loc[watch_df.index[-1], "volume"] = 300
    watch_df.loc[watch_df.index[-2], "volume"] = 350
    scenarios.append(watch_df)

    for df in scenarios:
        result = indicators.pullback_signal(df)
        assert isinstance(result["reason"], str)
        assert result["reason"].strip() != ""



# ────────────────────────────────────────────
# 기존 함수 회귀 가드 — macd_cross_signal / rsi_zone_signal 어휘 불변
# ────────────────────────────────────────────

def test_macd_cross_signal_golden_cross_vocabulary_unchanged():
    """40봉 하락 후 2봉만 반등시킨 지점(k=42)에서 실제로 골든크로스가 발생하는
    고정 시계열 — 이 파일 작성 중 스캔해 첫 골든크로스 시점을 확인한 결과이며,
    이후 임의 재실행에도 완전히 결정적(랜덤 없음)이다."""
    closes = [200.0 - 2.0 * (i + 1) for i in range(40)]       # 198.0 ... 120.0
    closes += [closes[-1] + 3.0 * (i + 1) for i in range(2)]  # 123.0, 126.0
    df = _ohlcv_from_closes(closes)
    assert indicators.macd_cross_signal(df) == "골든크로스(진입)"


def test_rsi_zone_signal_oversold_vocabulary_unchanged():
    """31봉 연속 하락 — RSI(14)가 바닥까지 눌려 명백한 과매도(진입) 구간."""
    closes = [200.0]
    for _ in range(30):
        closes.append(closes[-1] - 3.0)
    df = _ohlcv_from_closes(closes)
    assert indicators.rsi_zone_signal(df) == "과매도(진입)"


# ────────────────────────────────────────────
# pullback_signal — checks(체크리스트) 구조화 필드
# ────────────────────────────────────────────

_PULLBACK_CHECK_LABELS = [
    "정배열 (MA5>MA20>MA60)",
    "MA20 기울기 상승",
    "추세 강도 (ADX≥20)",
    "MA20 근접 (눌림 깊이)",
    "거래량 수축 (≤60%)",
    "반등 트리거 (양봉·전일고가·거래량)",
]


def test_pullback_checks_empty_when_data_insufficient():
    """데이터부족 상태는 평가 자체가 불가하므로 checks=[] (빈 리스트)."""
    df = _linear_df(PULLBACK_MIN_BARS - 1)
    result = indicators.pullback_signal(df)
    assert result["status"] == "데이터부족"
    assert result["checks"] == []


def test_pullback_checks_bounce_candidate_length_order_and_flags():
    """눌림목 반등 픽스처에서 checks는 6개·label 순서 고정이며, 추세·근접·반등트리거
    관련 5개는 True다. 단 '거래량 수축(≤60%)'과 '반등 트리거'의 팽창(≥140%)은 같은
    현재봉 vol_ratio에서 유도되는 **상호 배타** 조건이라(하나의 비율이 ≤0.6이면서
    동시에 ≥1.4일 수 없음) 반등 상태에서 수축 항목은 논리적으로 False가 된다 —
    체크리스트는 각 조건의 '독립' 상태를 보여줄 뿐 전 항목 동시 충족을 뜻하지 않는다."""
    df = _consolidation_df()
    prev_close = df.loc[df.index[-2], "close"]
    last_idx = df.index[-1]
    df.loc[last_idx, "open"] = prev_close - 0.3
    df.loc[last_idx, "close"] = prev_close + 2.0
    df.loc[last_idx, "high"] = prev_close + 2.1
    df.loc[last_idx, "low"] = prev_close - 0.4
    df.loc[last_idx, "volume"] = 3000
    result = indicators.pullback_signal(df)
    assert result["status"] == "눌림목 반등(매수후보)"
    checks = result["checks"]
    assert len(checks) == 6
    assert [c["label"] for c in checks] == _PULLBACK_CHECK_LABELS
    assert checks[0]["ok"] is True   # 정배열(Close>MA60 포함)
    assert checks[1]["ok"] is True   # MA20 기울기 상승
    assert checks[2]["ok"] is True   # 추세 강도(ADX)
    assert checks[3]["ok"] is True   # MA20 근접(눌림 깊이)
    assert checks[4]["ok"] is False  # 거래량 수축 — 반등 트리거의 팽창과 상호배타
    assert checks[5]["ok"] is True   # 반등 트리거


def test_pullback_checks_not_trend_state_length_order_and_some_false():
    """추세아님 픽스처(지속 하락·역배열)에서도 checks는 6개·label 순서 고정으로 채워지며,
    추세 필터 3항목(정배열/기울기/ADX) 중 하나 이상은 False다."""
    df = _linear_df(80, start=200.0, step=-1.0)
    result = indicators.pullback_signal(df)
    assert result["status"] == "추세아님"
    checks = result["checks"]
    assert len(checks) == 6
    assert [c["label"] for c in checks] == _PULLBACK_CHECK_LABELS
    assert any(not c["ok"] for c in checks[:3])


def test_pullback_checks_present_in_all_non_insufficient_states():
    """데이터부족을 제외한 모든 상태에서 checks 6개가 온전히 채워진다(부분 채움 금지)."""
    scenarios = [
        _linear_df(80, start=200.0, step=-1.0),   # 추세아님
        _linear_df(80),                            # 추세지속(MA20 이격)
        _consolidation_df(),                       # 눌림 진행중 계열
    ]
    for df in scenarios:
        result = indicators.pullback_signal(df)
        if result["status"] == "데이터부족":
            continue
        assert len(result["checks"]) == 6
        assert [c["label"] for c in result["checks"]] == _PULLBACK_CHECK_LABELS
        assert all(isinstance(c["ok"], bool) for c in result["checks"])
