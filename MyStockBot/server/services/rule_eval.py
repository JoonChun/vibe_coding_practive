"""판정 룰 평가 하네스 — "이 가중치를 바꿀 근거가 있는가?"에 답하는 오프라인 도구.

## 왜 필요한가
src/decision_rules.py 의 점수 가중치(MACD ±2/±1, RSI ±1, 재무 ±1씩)와 등급 임계값
(단기 ±2, 장기 ±3)은 전부 손으로 정한 값이고, 이 저장소에는 그것을 데이터로 확인한 기록이
없었다. 백테스트 카드는 "현행 룰의 성적"만 보여주고 룰 개선으로 되먹이는 경로가 없었다.

## 이 도구가 하는 일 (그리고 하지 않는 일)
**가장 중요한 출력은 "그 질문에 답할 수 있는 데이터가 있는가"다.** 먼저 검출력(MDE)을 계산해
"현재 이력으로는 이 정도 크기의 차이를 구분할 수 없다"고 말한다. 가중치 ±1 조정의 기대효과는
보통 1~3pp 인데 종목당 400봉·horizon 20 이면 독립 관측이 수십 건뿐이라 MDE 가 그보다 크다 —
그 경우 정직한 답은 "모르겠다"이고, 숫자를 바꾸지 않는 것이 정답이다.

담은 것:
  · power_report  — 독립 표본 수(겹침·종목간 상관 보정)와 MDE. **먼저 봐야 하는 것.**
  · base rate     — 무조건부 P(선행수익>0). 상승장에서 base rate 60%면 매수 적중률 60%는
                    정보량 0이다. 적중률은 반드시 이 값 대비 lift 로만 읽는다.
  · monotonicity  — 점수 버킷별 평균 선행수익 + 점수↔수익 순위상관(Spearman ρ).
                    가중치가 의미 있다면 점수가 높을수록 수익이 높아야 한다. 변형 20개를
                    돌리지 않고 가중치를 검증하는 단일 사전지정 검정이라 다중검정 함정이 없다.
  · comparators   — always_buy(=buy&hold) / always_watch. 기준선을 이겼지만 always_buy 에
                    지는 변형은 개선이 아니라 상승장 재발견이다.
  · paired compare — 두 룰이 갈린 봉만 모아 비교하고 **불일치쌍 수를 함께** 낸다.

일부러 넣지 않은 것(그리고 그 이유):
  · 실험 원장·holdout 예산·블록 부트스트랩·best-of-K 귀무분포 — 이건 모두 "여러 변형 중
    승자를 고를 때" 과최적화를 막는 장치다. 위 MDE 계산이 "지금 데이터로는 승자를 고를 수
    없다"고 답하는 동안에는 그 장치를 만들 이유가 없다(쓸 일 없는 기계). 실제로 채택 결정을
    시도할 만큼 이력이 쌓였다면 그때 반드시 추가해야 하며, 필요한 목록은 prd.md §22 에 적었다.

## 한계 (반드시 읽을 것)
  · **재무 가중치는 이 도구로 검증할 수 없다.** 과거 PER/PBR/ROE 이력이 없어 재무 점수는
    항상 0이다. 재무 관련 변형은 결과가 기준선과 완전히 동일하게 나오는데, 이걸 "차이 없음"
    으로 읽으면 거짓이다 → fundamentals_testable=False 로 명시한다.
  · 진입가가 판정 시점 종가와 같다(선행수익률 정의). 절대 수치는 낙관 편향이고, 변형 간
    비교에는 중립이다.
  · 수수료·세금·슬리피지 미반영. 회전율이 다른 변형끼리는 이 누락이 편향이 된다 →
    turnover 를 함께 낸다.
  · 유니버스가 사용자의 현재 관심종목이면 사후 선택 편향이 있다(잘 된 종목만 남아 있다).
"""
import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 적중률 신뢰구간·MDE 계산용 z값(95%).
_Z_95 = 1.96

# 점수↔수익 단조성 판단에 필요한 최소 버킷 표본(이보다 적은 버킷은 평균이 무의미).
_MIN_BUCKET_SAMPLES = 5


@dataclass(frozen=True)
class Series:
    """평가 대상 한 종목의 시계열. closes 는 오름차순·양수(정제 완료)."""
    code: str
    closes: list[float]
    # 봉 인덱스 → 달력 블록. 종목 간 동일 시점 상관을 보정할 때 쓴다(없으면 인덱스 기반 근사).
    day_index: list[int] | None = None


@dataclass(frozen=True)
class Observation:
    """한 종목의 한 봉에서 나온 관측 1건."""
    code: str
    bar: int
    cal_block: int
    score: int
    view: str
    fwd_pct: float


def _rank(values: list[float]) -> list[float]:
    """평균 순위(동순위는 평균) — Spearman 계산용."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman 순위상관. 표본 부족·분산 0 이면 None. (scipy 의존을 늘리지 않기 위해 직접 구현)"""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _rank(xs), _rank(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def wilson_interval(hits: int, n: int) -> list[float] | None:
    """이항 비율 Wilson 95% CI [하한%, 상한%]. backtest._wilson_interval 과 동일 규칙."""
    from .backtest import _wilson_interval

    return _wilson_interval(hits, n)


def effective_sample(indices: list[int], horizon: int) -> int:
    """겹침 보정 독립 표본 수. backtest._effective_sample 재사용."""
    from .backtest import _effective_sample

    return _effective_sample(indices, horizon)


def cluster_sample(observations: list[Observation]) -> int:
    """종목 간 동일 시점 상관까지 보정한 표본 수 = 신호가 존재하는 서로 다른 달력 블록 수.

    같은 날 여러 종목이 동시에 골든크로스를 내면 그건 독립 관측 N건이 아니라 사실상 1건이다
    (같은 시장 움직임을 본다). 종목별 겹침 보정만 하고 그냥 합치면 표본이 종목 수만큼
    부풀어 신뢰구간이 과신된다.
    """
    return len({o.cal_block for o in observations})


def minimum_detectable_effect(n_eff: int, p: float = 0.5) -> float | None:
    """두 룰의 적중률 차이를 구분하려면 최소 몇 pp 여야 하는지(95% 기준, 근사).

    두 비율 비교의 표준오차 sqrt(2p(1-p)/n) 에 z를 곱한 값. n_eff 가 작으면 이 값이 커지고,
    기대효과가 이보다 작으면 **실험 자체가 무의미하다** — 유의해 보이는 결과가 나와도 노이즈다.
    """
    if n_eff <= 0:
        return None
    return round(_Z_95 * math.sqrt(2 * p * (1 - p) / n_eff) * 100, 1)


def label_series(closes: list[float]) -> tuple[list[str], list[str]]:
    """종가 시계열 → (MACD 라벨, RSI 라벨) 시계열. 룰셋과 무관하므로 변형마다 재계산하지 않는다.

    MACD(EMA)·RSI(Wilder)는 인과적이라 전 구간 1회 계산으로 각 시점 prefix 계산과 동일하다
    (backtest._build_view_at 와 같은 근거). 가중치만 바꾸는 변형 N개가 이 결과를 공유한다.
    """
    import pandas as pd
    import ta.momentum
    import ta.trend

    import decision_rules as rules
    import indicators
    from config import MACD_FAST, MACD_SIGNAL, MACD_SLOW, RSI_PERIOD

    close = pd.Series(closes, dtype="float64")
    macd_obj = ta.trend.MACD(
        close=close, window_fast=MACD_FAST, window_slow=MACD_SLOW, window_sign=MACD_SIGNAL
    )
    macd_line = macd_obj.macd().tolist()
    signal_line = macd_obj.macd_signal().tolist()
    rsi = ta.momentum.RSIIndicator(close=close, window=RSI_PERIOD).rsi().tolist()

    macd_labels = [rules.NO_DATA]
    for i in range(1, len(closes)):
        macd_labels.append(
            indicators.macd_label_from_pair(
                macd_line[i - 1], macd_line[i], signal_line[i - 1], signal_line[i]
            )
        )
    rsi_labels = [indicators.rsi_label_from_value(v) for v in rsi]
    return macd_labels, rsi_labels


def observe(series: Series, ruleset, horizon: int, warmup: int) -> list[Observation]:
    """한 종목에 룰셋을 재적용해 관측 목록을 만든다.

    warmup 은 모든 변형에 **공통**으로 주입해야 한다 — MACD 파라미터가 다른 변형은 필요한
    준비 봉수가 달라서, 각자 자기 warmup 을 쓰면 평가 구간이 달라지고 같은 데이터로 비교한
    게 아니게 된다.
    """
    import decision_rules as rules

    closes = series.closes
    n = len(closes)
    macd_labels, rsi_labels = label_series(closes)
    day_index = series.day_index or list(range(n))

    out: list[Observation] = []
    for t in range(warmup, n - horizon):
        entry = closes[t]
        if entry <= 0:
            continue
        macd_label, rsi_label = macd_labels[t], rsi_labels[t]
        if macd_label == rules.NO_DATA and rsi_label == rules.NO_DATA:
            continue
        tech = ruleset.macd_score(macd_label) + ruleset.rsi_score(rsi_label)
        # 재무 과거값이 없어 fund=0 → 확증 규칙은 이 경로에서 발동하지 않는다(tech==score).
        view = ruleset.level5(tech, ruleset.long_strong, confirm=tech)
        out.append(Observation(
            code=series.code,
            bar=t,
            cal_block=day_index[t] // max(1, horizon),
            score=tech,
            view=view,
            fwd_pct=(closes[t + horizon] - entry) / entry * 100,
        ))
    return out


def _side_stats(obs: list[Observation], views: set[str], win, horizon: int,
                base_rate: float | None) -> dict:
    picked = [o for o in obs if o.view in views]
    if not picked:
        return {
            "signals": 0, "effective_signals": 0, "cluster_signals": 0,
            "hit_rate": None, "hit_rate_ci": None, "lift_pp": None,
            "avg_forward_pct": None, "mde_pp": None, "low_confidence": True,
        }
    hits = sum(1 for o in picked if win(o.fwd_pct))
    total = len(picked)
    n_within = sum(
        effective_sample([o.bar for o in picked if o.code == code], horizon)
        for code in {o.code for o in picked}
    )
    n_cluster = cluster_sample(picked)
    hit_rate = hits / total * 100
    return {
        "signals": total,
        "effective_signals": n_within,
        "cluster_signals": n_cluster,
        "hit_rate": round(hit_rate, 1),
        # CI 는 가장 보수적인 표본(달력 클러스터)으로 — 종목 수만큼 표본이 부풀지 않도록.
        "hit_rate_ci": wilson_interval(round(hits / total * n_cluster), n_cluster),
        "lift_pp": None if base_rate is None else round(hit_rate - base_rate, 1),
        "avg_forward_pct": round(sum(o.fwd_pct for o in picked) / total, 2),
        "mde_pp": minimum_detectable_effect(n_cluster),
        "low_confidence": n_cluster < 30,
    }


def monotonicity(obs: list[Observation]) -> dict:
    """점수 버킷별 평균 선행수익 + 점수↔수익 순위상관.

    가중치가 의미 있다면 점수가 높을수록 평균 선행수익이 높아야 한다. 이건 변형을 여러 개
    돌려 최고를 고르는 방식이 아니라 **하나의 사전지정 검정**이므로 다중검정 함정이 없다.
    종목별 ρ 의 부호 분포도 함께 낸다 — "30종목 중 26종목에서 양수"는 pooled ρ 하나보다
    훨씬 강한 증거다.
    """
    buckets: dict[int, list[float]] = {}
    for o in obs:
        buckets.setdefault(o.score, []).append(o.fwd_pct)

    table = []
    for score in sorted(buckets):
        vals = buckets[score]
        table.append({
            "score": score,
            "n": len(vals),
            "avg_forward_pct": round(sum(vals) / len(vals), 2),
            "reliable": len(vals) >= _MIN_BUCKET_SAMPLES,
        })

    pooled = spearman([float(o.score) for o in obs], [o.fwd_pct for o in obs])

    per_code = {}
    for code in sorted({o.code for o in obs}):
        sub = [o for o in obs if o.code == code]
        rho = spearman([float(o.score) for o in sub], [o.fwd_pct for o in sub])
        if rho is not None:
            per_code[code] = rho
    positives = sum(1 for r in per_code.values() if r > 0)

    return {
        "buckets": table,
        "spearman_pooled": pooled,
        "spearman_by_code": per_code,
        "codes_positive": positives,
        "codes_total": len(per_code),
    }


def evaluate(panel: list[Series], ruleset, horizon: int = 20,
             warmup: int = 35) -> dict:
    """룰셋 하나를 패널 전체에 재적용해 지표를 낸다."""
    import decision_rules as rules

    obs: list[Observation] = []
    skipped = []
    for series in panel:
        if len(series.closes) < warmup + horizon + 1:
            skipped.append(series.code)
            continue
        obs.extend(observe(series, ruleset, horizon, warmup))

    if not obs:
        return {
            "rule_id": ruleset.id, "horizon": horizon, "observations": 0,
            "skipped_codes": skipped, "base_rate_pct": None,
            "buy": _side_stats([], set(), lambda f: f > 0, horizon, None),
            "sell": _side_stats([], set(), lambda f: f < 0, horizon, None),
            "monotonicity": {"buckets": [], "spearman_pooled": None,
                             "spearman_by_code": {}, "codes_positive": 0, "codes_total": 0},
            "time_in_market_pct": None, "turnover_per_year": None,
            "fundamentals_testable": False,
            "notes": ["평가할 관측이 없습니다(이력 부족)."],
        }

    # base rate = 무조건부 P(선행수익 > 0). 적중률은 이 값 대비 lift 로만 의미가 있다.
    up_count = sum(1 for o in obs if o.fwd_pct > 0)
    base_rate = up_count / len(obs) * 100
    # CI 는 겹침·종목간 상관을 보정한 클러스터 표본으로 계산한다 → 적중 수도 같은 비율로
    # 스케일해야 한다(원 적중 수를 그대로 넘기면 p>1 이 된다).
    base_cluster = cluster_sample(obs)
    base_rate_ci = wilson_interval(
        round(up_count / len(obs) * base_cluster), base_cluster
    )

    buy_views = {rules.VIEW_BUY, rules.VIEW_STRONG_BUY}
    sell_views = {rules.VIEW_SELL, rules.VIEW_STRONG_SELL}

    in_market = sum(1 for o in obs if o.view in buy_views)
    # 회전율: 종목별로 매수/현금 상태가 뒤집힌 횟수를 연율화(1년 ≈ 246 거래일).
    flips = 0
    for code in {o.code for o in obs}:
        sub = sorted((o for o in obs if o.code == code), key=lambda o: o.bar)
        prev = None
        for o in sub:
            cur = o.view in buy_views
            if prev is not None and cur != prev:
                flips += 1
            prev = cur
    turnover = round(flips / len(obs) * 246, 1) if obs else None

    return {
        "rule_id": ruleset.id,
        "horizon": horizon,
        "warmup": warmup,
        "observations": len(obs),
        "codes": sorted({o.code for o in obs}),
        "skipped_codes": skipped,
        "base_rate_pct": round(base_rate, 1),
        "base_rate_ci": base_rate_ci,
        "cluster_samples": base_cluster,
        "buy": _side_stats(obs, buy_views, lambda f: f > 0, horizon, base_rate),
        "sell": _side_stats(obs, sell_views, lambda f: f < 0, horizon, 100 - base_rate),
        "monotonicity": monotonicity(obs),
        "time_in_market_pct": round(in_market / len(obs) * 100, 1),
        "turnover_per_year": turnover,
        # 재무 과거값이 없으므로 재무 가중치는 이 하네스로 검증 불가.
        "fundamentals_testable": False,
        "notes": [
            "재무 지표 과거값이 없어 재무 가중치는 검증할 수 없습니다(항상 0점으로 계산).",
            "수수료·세금·슬리피지 미반영 — 회전율이 다른 룰끼리는 비교가 낙관적으로 기웁니다.",
            "적중률은 base_rate 대비 lift 로만 해석하세요(상승 구간에서는 아무 신호나 잘 맞습니다).",
        ],
        "_observations": obs,  # 내부용(짝지은 비교에서 사용) — 리포트 출력 시 제외
    }


def compare(baseline_result: dict, variant_result: dict) -> dict:
    """두 룰의 짝지은 비교 — 판정이 갈린 봉만 대상으로 하고 불일치쌍 수를 함께 낸다.

    독립 CI 두 개의 겹침으로 비교하면 같은 데이터를 본다는 사실을 버려 검정력을 낭비한다.
    불일치쌍이 몇 건인지 반드시 봐야 한다 — 12건이면 어떤 차이도 결론이 아니다.
    """
    import decision_rules as rules

    base_obs = {(o.code, o.bar): o for o in baseline_result.get("_observations", [])}
    var_obs = {(o.code, o.bar): o for o in variant_result.get("_observations", [])}
    shared = sorted(set(base_obs) & set(var_obs))

    buy_views = {rules.VIEW_BUY, rules.VIEW_STRONG_BUY}
    discordant = [k for k in shared
                  if (base_obs[k].view in buy_views) != (var_obs[k].view in buy_views)]

    base_wins = sum(
        1 for k in discordant
        if (base_obs[k].view in buy_views) and base_obs[k].fwd_pct > 0
    )
    var_wins = sum(
        1 for k in discordant
        if (var_obs[k].view in buy_views) and var_obs[k].fwd_pct > 0
    )

    base_hit = baseline_result["buy"]["hit_rate"]
    var_hit = variant_result["buy"]["hit_rate"]
    lift = None if base_hit is None or var_hit is None else round(var_hit - base_hit, 1)

    n_cluster = min(
        baseline_result["buy"]["cluster_signals"], variant_result["buy"]["cluster_signals"]
    )
    mde = minimum_detectable_effect(n_cluster)
    conclusive = (
        lift is not None and mde is not None and abs(lift) > mde and len(discordant) >= 30
    )

    if lift is None:
        reason = (
            f"한쪽 룰이 매수 신호를 내지 않아 적중률을 비교할 수 없습니다"
            f"(기준선 {baseline_result['buy']['signals']}건 / "
            f"변형 {variant_result['buy']['signals']}건)"
        )
    elif conclusive:
        reason = f"효과 {lift}pp 가 검출한계 {mde}pp 를 넘고 불일치쌍 {len(discordant)}건"
    else:
        reason = (
            f"효과 {lift}pp vs 검출한계 {mde}pp, 불일치쌍 {len(discordant)}건 "
            f"— 이 데이터로는 차이를 주장할 수 없습니다"
        )

    return {
        "baseline": baseline_result["rule_id"],
        "variant": variant_result["rule_id"],
        "shared_bars": len(shared),
        "discordant_pairs": len(discordant),
        "baseline_wins_on_discordant": base_wins,
        "variant_wins_on_discordant": var_wins,
        "buy_hit_lift_pp": lift,
        "mde_pp": mde,
        # 사전 규칙: 효과가 MDE 를 넘고 불일치쌍이 30건 이상일 때만 결론을 말한다.
        "verdict": "difference_detected" if conclusive else "inconclusive",
        "verdict_reason": reason,
    }


def power_report(panel: list[Series], horizon: int = 20, warmup: int = 35) -> dict:
    """**실험 전에 먼저 볼 것** — 이 패널로 어느 크기의 차이를 검출할 수 있는가.

    MDE 가 기대효과보다 크면 어떤 변형 실험도 노이즈만 잡는다. 그 경우 정직한 결론은
    "판단할 근거가 없으므로 현행 값을 유지한다"이다.
    """
    import decision_rules as rules

    total_bars = 0
    usable_codes = []
    blocks: set[int] = set()
    for series in panel:
        n = len(series.closes)
        total_bars += n
        if n < warmup + horizon + 1:
            continue
        usable_codes.append(series.code)
        day_index = series.day_index or list(range(n))
        for t in range(warmup, n - horizon):
            blocks.add(day_index[t] // max(1, horizon))

    n_cluster = len(blocks)
    mde = minimum_detectable_effect(n_cluster)
    return {
        "codes": len(panel),
        "usable_codes": len(usable_codes),
        "total_bars": total_bars,
        "horizon": horizon,
        "warmup": warmup,
        "cluster_samples": n_cluster,
        "mde_pp": mde,
        "verdict": (
            "underpowered" if mde is None or mde > 3.0 else "usable"
        ),
        "explanation": (
            f"독립 관측 근사 {n_cluster}건 → 검출한계 약 {mde}pp. "
            f"가중치 ±1 조정의 기대효과는 보통 1~3pp 이므로, 이 값이 3pp 를 넘으면 "
            f"실험 결과가 유의해 보여도 노이즈로 설명된다."
            if mde is not None else
            "평가 가능한 관측이 없다(이력 부족)."
        ),
        "baseline_rule_id": rules.BASELINE.id,
    }


# ────────────────────────────────────────────
# 패널 로딩 (저장소 → Series)
# ────────────────────────────────────────────

def load_panel(codes: list[str] | None = None, max_bars: int = 400) -> list[Series]:
    """SQLite candles(1d) 저장소에서 패널을 만든다. codes 생략 시 활성 관심종목 전체.

    yfinance 폴백을 하지 않는다 — KIS 와 야후는 수정주가 규약이 달라 종목별로 소스가 섞이면
    룰 비교 자체가 무효가 된다. 이력이 부족한 종목은 그냥 제외하고 목록에 남긴다.
    """
    import db

    from .backtest import _sanitize_closes

    if codes is None:
        codes = [item["code"] for item in db.load_watchlist()]

    panel: list[Series] = []
    for code in codes:
        stored = db.get_candles_store(code, "1d", max_bars)
        if not stored:
            continue
        try:
            closes = _sanitize_closes([row.get("close") for row in stored])
        except ValueError:
            continue
        # 달력 블록 계산용 상대 일수 — t 값(epoch)이 있으면 실제 날짜 간격을 반영한다.
        ts = [row.get("t") for row in stored]
        if all(isinstance(v, int) for v in ts) and len(ts) > 1:
            first = ts[0]
            day_index = [max(0, (v - first) // 86400) for v in ts]
        else:
            day_index = list(range(len(closes)))
        panel.append(Series(code=code, closes=closes, day_index=day_index))
    return panel
