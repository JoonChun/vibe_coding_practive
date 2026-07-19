import { formatKrw } from "../utils/format";

interface BollingerTrackProps {
  upper: number | null;
  mid: number | null;
  lower: number | null;
  price: number | null;
}

/** 볼린저 밴드 미니 세로 트랙 — 상단/중간/하단 눈금 + 현재가 위치 마커 */
export function BollingerTrack({ upper, mid, lower, price }: BollingerTrackProps) {
  const hasBand =
    upper !== null && lower !== null && price !== null && upper > lower;

  return (
    <div className="bollinger-card">
      <h3 className="bollinger-card__title">Bollinger Band</h3>
      {hasBand ? (
        <BollingerVisual
          upper={upper as number}
          mid={mid}
          lower={lower as number}
          price={price as number}
        />
      ) : (
        <p className="bollinger-card__empty">데이터 부족</p>
      )}
      <p className="bollinger-card__caption">Price relative to ±2σ</p>
    </div>
  );
}

function BollingerVisual({
  upper,
  mid,
  lower,
  price,
}: {
  upper: number;
  mid: number | null;
  lower: number;
  price: number;
}) {
  const range = upper - lower;
  const rawFraction = (price - lower) / range;
  const clampedFraction = Math.max(0, Math.min(1, rawFraction));
  const outOfRange = rawFraction < 0 || rawFraction > 1;
  const markerTopPct = (1 - clampedFraction) * 100;

  const midFraction = mid !== null ? Math.max(0, Math.min(1, (mid - lower) / range)) : null;
  const midTopPct = midFraction !== null ? (1 - midFraction) * 100 : null;

  const ariaLabel = `볼린저 밴드: 상단 ${formatKrw(upper)}, 중간 ${
    mid !== null ? formatKrw(mid) : "정보 없음"
  }, 하단 ${formatKrw(lower)}, 현재가 ${formatKrw(price)}${
    outOfRange ? (rawFraction > 1 ? ", 상단 밴드 이탈" : ", 하단 밴드 이탈") : ""
  }`;

  return (
    <div className="bollinger-visual">
      <div className="bollinger-visual__track" role="img" aria-label={ariaLabel}>
        <span className="bollinger-visual__tick bollinger-visual__tick--upper" aria-hidden="true" />
        {midTopPct !== null ? (
          <span
            className="bollinger-visual__tick bollinger-visual__tick--mid"
            style={{ top: `${midTopPct}%` }}
            aria-hidden="true"
          />
        ) : null}
        <span className="bollinger-visual__tick bollinger-visual__tick--lower" aria-hidden="true" />
        <span
          className="bollinger-visual__marker"
          style={{ top: `${markerTopPct}%` }}
          aria-hidden="true"
        >
          <span className="bollinger-visual__dot" />
          <span className="bollinger-visual__price">{formatKrw(price)}</span>
        </span>
      </div>
      {outOfRange ? (
        <p className="bollinger-visual__out">
          {rawFraction > 1 ? "▲ 상단 밴드 이탈" : "▼ 하단 밴드 이탈"}
        </p>
      ) : null}
    </div>
  );
}
