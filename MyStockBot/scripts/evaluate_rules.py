"""판정 룰 평가 CLI — 가중치를 바꿀 근거가 있는지 확인하는 오프라인 도구.

사용법(MyStockBot 디렉터리에서):
    python scripts/evaluate_rules.py                     # 관심종목 전체, 기준선만
    python scripts/evaluate_rules.py --codes 005930,035720
    python scripts/evaluate_rules.py --horizon 20 --compare-variants
    python scripts/evaluate_rules.py --json             # 기계 판독용

**먼저 검출력(MDE)을 본다.** "underpowered" 로 나오면 어떤 변형 실험도 노이즈를 잡는 것이니
숫자를 바꾸지 말아야 한다. 자세한 배경은 server/services/rule_eval.py 모듈 docstring 참고.

이 스크립트는 판정 규칙을 **바꾸지 않는다.** 근거를 보여줄 뿐이고, 반영은 사람이
src/decision_rules.py 를 고쳐서 한다.
"""
import argparse
import json
import logging
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE_DIR))
sys.path.insert(0, str(_BASE_DIR / "src"))

from dotenv import load_dotenv

load_dotenv(_BASE_DIR / ".env")

import decision_rules as rules
from server.services import rule_eval

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _variants() -> list[rules.RuleSet]:
    """비교용 변형 — 사전 가설이 있는 것만. 격자탐색은 하지 않는다(과최적화).

    비교군(always_buy / always_watch)을 항상 포함한다. 기준선을 이겼지만 always_buy(=단순
    보유)에 지는 변형은 개선이 아니라 상승장을 재발견한 것이다.
    """
    return [
        # 가설: MACD 골든크로스의 +2 가 과대평가라면 ±1 로 낮춰도 성적이 유지될 것이다.
        rules.RuleSet(id="macd_flat", macd_scores={
            rules.MACD_GOLDEN_CROSS: 1, rules.MACD_ABOVE: 1,
            rules.MACD_BELOW: -1, rules.MACD_DEAD_CROSS: -1,
        }),
        # 가설: RSI 기여(±1)가 노이즈라면 제거해도 성적이 유지될 것이다.
        rules.RuleSet(id="no_rsi", rsi_scores={}),
        # 비교군: 임계값을 0 으로 내리면 사실상 항상 매수(=buy&hold)가 된다.
        rules.RuleSet(id="always_buy_ish", weak_cutoff=-99, long_strong=-99),
        # 비교군: 임계값을 크게 올리면 사실상 항상 관망.
        rules.RuleSet(id="always_watch_ish", weak_cutoff=99, long_strong=99),
    ]


def _fmt_side(name: str, side: dict) -> list[str]:
    if side["signals"] == 0:
        return [f"  {name}: 신호 없음"]
    ci = side["hit_rate_ci"]
    ci_text = f"{ci[0]:.0f}~{ci[1]:.0f}%" if ci else "—"
    return [
        f"  {name}: 적중률 {side['hit_rate']}% (95% CI {ci_text})"
        f"{'  ⚠참고치' if side['low_confidence'] else ''}",
        f"      lift {side['lift_pp']}pp · 평균 선행수익 {side['avg_forward_pct']}%",
        f"      신호 {side['signals']}건 → 겹침보정 {side['effective_signals']}건 "
        f"→ 달력클러스터 {side['cluster_signals']}건 · 검출한계 {side['mde_pp']}pp",
    ]


def _print_report(power: dict, base: dict, comparisons: list[dict]) -> None:
    lines = []
    lines.append("=" * 74)
    lines.append("판정 룰 평가 리포트")
    lines.append("=" * 74)
    lines.append("")
    lines.append("[1] 검출력 — 이 데이터로 무엇을 판단할 수 있는가")
    lines.append(f"  종목 {power['codes']}개(사용가능 {power['usable_codes']}개) · "
                 f"총 {power['total_bars']}봉 · horizon {power['horizon']}일")
    lines.append(f"  달력 클러스터 표본 {power['cluster_samples']}건 · "
                 f"검출한계(MDE) {power['mde_pp']}pp")
    lines.append(f"  판정: {power['verdict'].upper()}")
    lines.append(f"  → {power['explanation']}")
    if power["verdict"] == "underpowered":
        lines.append("")
        lines.append("  ⚠ 이 데이터로는 가중치 변경의 효과를 검출할 수 없습니다.")
        lines.append("    정직한 결론은 '근거가 없으므로 현행 값 유지'입니다.")
        lines.append("    아래 숫자는 참고용이며, 이걸로 룰을 바꾸면 노이즈에 맞추는 것입니다.")
    lines.append("")

    lines.append(f"[2] 기준선({base['rule_id']}) 성적")
    lines.append(f"  관측 {base['observations']}건 · 종목 {len(base.get('codes', []))}개"
                 + (f" · 제외 {base['skipped_codes']}" if base["skipped_codes"] else ""))
    lines.append(f"  base rate(무조건부 상승확률) {base['base_rate_pct']}%"
                 " ← 적중률은 이 값 대비로만 의미가 있습니다")
    lines.extend(_fmt_side("매수", base["buy"]))
    lines.extend(_fmt_side("매도", base["sell"]))
    lines.append(f"  시장 노출 {base['time_in_market_pct']}% · "
                 f"연 회전율 {base['turnover_per_year']}회")
    lines.append("")

    mono = base["monotonicity"]
    lines.append("[3] 점수↔선행수익 단조성 — 가중치가 의미 있는지 보는 단일 검정")
    lines.append(f"  Spearman ρ(pooled) = {mono['spearman_pooled']}")
    lines.append(f"  종목별 ρ 양수 {mono['codes_positive']}/{mono['codes_total']}개")
    for row in mono["buckets"]:
        flag = "" if row["reliable"] else "  (표본부족)"
        lines.append(f"    점수 {row['score']:>+3}: 평균 {row['avg_forward_pct']:>+7.2f}% "
                     f"(n={row['n']}){flag}")
    lines.append("  → ρ 가 0 근처거나 버킷 평균이 단조가 아니면, 점수의 크기가 수익과")
    lines.append("    관계없다는 뜻입니다(가중치를 정교하게 만들 근거가 없음).")
    lines.append("")

    if comparisons:
        lines.append(f"[4] 변형 비교 (짝지은 — 판정이 갈린 봉만) · 변형 {len(comparisons)}개")
        lines.append(f"  ⚠ 변형 {len(comparisons)}개를 동시에 비교했습니다. 이 중 성적이 가장")
        lines.append("    좋은 것을 골라 채택하면 그것만으로 과최적화입니다 — 순수한 노이즈에서도")
        lines.append(f"    {len(comparisons)}개 중 하나는 좋아 보입니다. 아래 결과는 '가설 검토'용이며")
        lines.append("    채택 근거로 쓸 수 없습니다(best-of-K 귀무분포 검정이 아직 없음).")
        for c in comparisons:
            lift = c["buy_hit_lift_pp"]
            lift_text = "—" if lift is None else f"{lift}pp"
            mde_text = "—" if c["mde_pp"] is None else f"{c['mde_pp']}pp"
            lines.append(f"  {c['variant']} vs {c['baseline']}: {c['verdict'].upper()}")
            lines.append(f"      매수 적중률 차이 {lift_text} · "
                         f"불일치쌍 {c['discordant_pairs']}건 · 검출한계 {mde_text}")
            lines.append(f"      → {c['verdict_reason']}")
        lines.append("")

    lines.append("[5] 한계")
    for note in base["notes"]:
        lines.append(f"  · {note}")
    lines.append("  · 실험 원장·holdout 예산·블록 부트스트랩·best-of-K 귀무분포는 아직 없습니다.")
    lines.append("    변형 여러 개 중 승자를 실제로 '채택'하려면 그 장치가 먼저 필요합니다")
    lines.append("    (prd.md §22 참고). 지금은 검출력이 부족해 채택 결정 자체가 불가합니다.")
    lines.append("=" * 74)
    print("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="판정 룰 평가 하네스")
    parser.add_argument("--codes", default="", help="쉼표 구분 종목코드(기본: 활성 관심종목 전체)")
    parser.add_argument("--horizon", type=int, default=20, help="선행수익률 기간(거래일)")
    parser.add_argument("--max-bars", type=int, default=400, help="종목당 사용할 최근 일봉 수")
    parser.add_argument("--compare-variants", action="store_true",
                        help="사전 가설이 있는 변형 및 비교군과 짝지은 비교 수행")
    parser.add_argument("--json", action="store_true", help="JSON 출력(기계 판독용)")
    args = parser.parse_args()

    codes = [c.strip() for c in args.codes.split(",") if c.strip()] or None
    panel = rule_eval.load_panel(codes, max_bars=args.max_bars)
    if not panel:
        logger.warning(
            "평가할 일봉 이력이 없습니다. 웹앱을 띄워 관심종목을 등록하면 수집 사이클마다 "
            "candles(1d) 가 누적됩니다."
        )
        return 1

    power = rule_eval.power_report(panel, horizon=args.horizon)
    base = rule_eval.evaluate(panel, rules.BASELINE, horizon=args.horizon)

    comparisons = []
    if args.compare_variants:
        for variant in _variants():
            result = rule_eval.evaluate(panel, variant, horizon=args.horizon)
            comparisons.append(rule_eval.compare(base, result))

    if args.json:
        payload = {
            "power": power,
            "baseline": {k: v for k, v in base.items() if not k.startswith("_")},
            "comparisons": comparisons,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_report(power, base, comparisons)
    return 0


if __name__ == "__main__":
    sys.exit(main())
