import {
  ColorType,
  CrosshairMode,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { getCandles } from "../api";
import type { CandleItem, CandlesResponse, LiveBar, Timeframe } from "../types";
import { SourceBadge } from "./SourceBadge";

interface CandleChartProps {
  code: string;
  /** WS bar_update로 갱신되는 이 code의 타임프레임별 진행중(미마감) 봉 — useTickStream().liveBars[code] */
  liveBars?: Partial<Record<Timeframe, LiveBar>>;
  /** tickStream.connected && tickStream.kisConnected — 툴바 LIVE 태그 노출 조건(연결 살아있을 때만) */
  wsConnected?: boolean;
}

const UP_COLOR = "#dc2626"; // 양봉 적색 (국내 HTS 관행)
const DOWN_COLOR = "#2563eb"; // 음봉 청색
const UP_VOLUME_COLOR = "rgba(220, 38, 38, 0.5)";
const DOWN_VOLUME_COLOR = "rgba(37, 99, 235, 0.5)";

const MINUTE_TFS = ["1m", "5m", "15m", "30m", "60m", "120m", "240m"] as const;

type MinuteTf = (typeof MINUTE_TFS)[number];

const MINUTE_LABEL: Record<MinuteTf, string> = {
  "1m": "1분",
  "5m": "5분",
  "15m": "15분",
  "30m": "30분",
  "60m": "60분",
  "120m": "120분",
  "240m": "240분",
};

const PERIOD_BUTTONS: { value: Timeframe; label: string }[] = [
  { value: "1d", label: "일" },
  { value: "1w", label: "주" },
  { value: "1M", label: "월" },
  { value: "1y", label: "년" },
];

const TF_ARIA_LABEL: Record<Timeframe, string> = {
  "1m": "1분봉",
  "5m": "5분봉",
  "15m": "15분봉",
  "30m": "30분봉",
  "60m": "60분봉",
  "120m": "120분봉",
  "240m": "240분봉",
  "1d": "일봉",
  "1w": "주봉",
  "1M": "월봉",
  "1y": "년봉",
};

const MA_CONFIG = [
  { period: 5, color: "#16a34a", label: "MA5" },
  { period: 20, color: "#dc2626", label: "MA20" },
  { period: 60, color: "#f59e0b", label: "MA60" },
  { period: 120, color: "#8b5cf6", label: "MA120" },
] as const;

function isMinuteTf(tf: Timeframe): boolean {
  return (MINUTE_TFS as readonly string[]).includes(tf);
}

// WS bar_update가 실어나르는 tf 범위 — 분봉 7종 + 일봉(백엔드 계약: 1w/1M/1y는 오지 않음).
// 와이어프레임(§5)은 "분봉 한정"을 가정으로 남겼으나, 백엔드 계약에 1d가 이미 포함돼 있어 확정.
const LIVE_CAPABLE_TFS = new Set<Timeframe>([...MINUTE_TFS, "1d"]);

function isLiveCapableTf(tf: Timeframe): boolean {
  return LIVE_CAPABLE_TFS.has(tf);
}

/** open/high/low/close/volume이 모두 유효한 숫자로 채워진 캔들. */
type ValidCandle = CandleItem & {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

/** 백엔드가 open/high/low/close/volume의 null을 반환할 수 있으므로 방어적으로 걸러낸다. */
function isValidCandle(item: CandleItem): item is ValidCandle {
  return (
    Number.isFinite(item.t) &&
    Number.isFinite(item.open) &&
    Number.isFinite(item.high) &&
    Number.isFinite(item.low) &&
    Number.isFinite(item.close) &&
    Number.isFinite(item.volume)
  );
}

function computeMovingAverage(bars: ValidCandle[], period: number): LineData[] {
  if (bars.length < period) return [];
  const result: LineData[] = [];
  let sum = 0;
  for (let i = 0; i < bars.length; i += 1) {
    sum += bars[i].close;
    if (i >= period) {
      sum -= bars[i - period].close;
    }
    if (i >= period - 1) {
      result.push({ time: bars[i].t as UTCTimestamp, value: sum / period });
    }
  }
  return result;
}

/**
 * 종목 상세용 멀티 타임프레임 캔들스틱 차트 (lightweight-charts).
 * 분봉(1·5·15·30·60·120·240)/일/주/월/년 전환, 거래량 오버레이, MA 5/20/60/120을 그린다.
 * tf·code 변경 시 이전 요청 응답은 무시하고(레이스 방지) 최신 데이터로만 갱신한다.
 */
export function CandleChart({ code, liveBars, wsConnected = false }: CandleChartProps) {
  const [tf, setTf] = useState<Timeframe>("1d");
  const [data, setData] = useState<CandlesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maSeriesRef = useRef<Partial<Record<number, ISeriesApi<"Line">>>>({});
  const requestIdRef = useRef(0);

  // 차트 인스턴스는 마운트 시 1회만 생성 — 리사이즈 대응 + 언마운트 시 정리.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "#ffffff" },
        textColor: "#45474c",
        fontFamily:
          '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", Roboto, Helvetica, Arial, sans-serif',
      },
      grid: {
        vertLines: { color: "#eae7e9" },
        horzLines: { color: "#eae7e9" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#c5c6cd" },
      timeScale: { borderColor: "#c5c6cd", timeVisible: false },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderVisible: false,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    });

    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
    });
    chart.priceScale("").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    const maSeries: Partial<Record<number, ISeriesApi<"Line">>> = {};
    for (const ma of MA_CONFIG) {
      maSeries[ma.period] = chart.addLineSeries({
        color: ma.color,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
    }

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    maSeriesRef.current = maSeries;

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        chart.applyOptions({ width, height });
      }
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
      maSeriesRef.current = {};
    };
  }, []);

  // 분봉은 시각(시:분) 표시, 일봉 이상은 날짜만 표시.
  useEffect(() => {
    chartRef.current?.applyOptions({
      timeScale: { timeVisible: isMinuteTf(tf) },
    });
  }, [tf]);

  // tf·code 변경 시 재조회. 응답이 도착했을 때 더 최신 요청이 나가 있으면 무시(레이스 방지).
  useEffect(() => {
    if (!code) {
      setData(null);
      setLoading(false);
      setErrorMessage(null);
      return;
    }

    const requestId = (requestIdRef.current += 1);
    setLoading(true);
    setErrorMessage(null);

    getCandles(code, tf)
      .then((res) => {
        if (requestIdRef.current !== requestId) return;
        setData(res);
        setLoading(false);
      })
      .catch(() => {
        if (requestIdRef.current !== requestId) return;
        setErrorMessage("차트 데이터를 불러오지 못했습니다.");
        setLoading(false);
      });
  }, [code, tf]);

  // 최신 데이터가 도착하면 캔들/거래량/이동평균 시리즈에 반영.
  useEffect(() => {
    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!candleSeries || !volumeSeries) return;

    const bars = (data?.items ?? [])
      .filter(isValidCandle)
      .slice()
      .sort((a, b) => a.t - b.t);

    const candleData: CandlestickData[] = bars.map((bar) => ({
      time: bar.t as UTCTimestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    const volumeData: HistogramData[] = bars.map((bar) => ({
      time: bar.t as UTCTimestamp,
      value: bar.volume,
      color: bar.close >= bar.open ? UP_VOLUME_COLOR : DOWN_VOLUME_COLOR,
    }));

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

    for (const ma of MA_CONFIG) {
      maSeriesRef.current[ma.period]?.setData(computeMovingAverage(bars, ma.period));
    }

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  // 진행중 봉(WS bar_update) 반영 — 전체 setData 재호출 없이 candleSeries.update()/volumeSeries.update()로
  // 증분 갱신한다. MA선은 설계상(와이어프레임 §5) 진행중 봉 동안 갱신하지 않는다.
  useEffect(() => {
    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!candleSeries || !volumeSeries) return;
    // 이력 미로딩 중이거나, code/tf 전환 직후 이전 이력이 아직 남아있는 레이스 상황이면
    // update()가 엉뚱한 종목/주기에 적용되거나 예외를 던질 수 있어 건너뛴다.
    if (loading || !data || data.code !== code || data.tf !== tf) return;

    const liveBar = liveBars?.[tf];
    if (!liveBar) return;

    const bars = (data.items ?? [])
      .filter(isValidCandle)
      .slice()
      .sort((a, b) => a.t - b.t);
    if (bars.length === 0) return;

    // lightweight-charts의 update()는 마지막 봉보다 이른 시각이 오면 예외를 던지므로 반드시 가드.
    // 같으면 해당 봉을 교체, 크면 새 봉으로 추가된다(둘 다 정상 동작).
    const lastBar = bars[bars.length - 1];
    if (liveBar.t < lastBar.t) return;

    candleSeries.update({
      time: liveBar.t as UTCTimestamp,
      open: liveBar.open,
      high: liveBar.high,
      low: liveBar.low,
      close: liveBar.close,
    });
    volumeSeries.update({
      time: liveBar.t as UTCTimestamp,
      value: liveBar.volume,
      color: liveBar.close >= liveBar.open ? UP_VOLUME_COLOR : DOWN_VOLUME_COLOR,
    });
  }, [liveBars, code, tf, data, loading]);

  function handleTfChange(next: Timeframe) {
    if (next === tf) return;
    setTf(next);
  }

  function handleMinuteSelect(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    if (!value) return;
    handleTfChange(value as Timeframe);
  }

  const isEmpty = !loading && data !== null && data.items.length === 0;
  const overlayMessage = errorMessage ?? (isEmpty ? "이 주기의 데이터가 없습니다" : null);

  return (
    <div className="candle-chart">
      <div className="candle-chart__toolbar">
        <div className="candle-chart__legend" aria-hidden="true">
          {MA_CONFIG.map((ma) => (
            <span key={ma.period} className="candle-chart__legend-item">
              <span
                className="candle-chart__legend-dot"
                style={{ backgroundColor: ma.color }}
              />
              {ma.label}
            </span>
          ))}
        </div>
        <div className="candle-chart__toolbar-right">
          {isLiveCapableTf(tf) && wsConnected ? (
            <span
              className="candle-chart__live-tag"
              title="마지막 봉은 미마감 상태로 실시간 갱신됩니다"
              aria-label="마지막 봉은 미마감 상태로 실시간 갱신됩니다"
            >
              <span className="live-strip__dot live-strip__dot--pulse" aria-hidden="true" />
              LIVE
            </span>
          ) : null}
          {data ? <SourceBadge source={data.source} /> : null}
        </div>
      </div>

      <div className="tf-bar" role="group" aria-label="차트 타임프레임 선택">
        <select
          className="tf-bar__select"
          aria-label="분봉 주기 선택"
          value={isMinuteTf(tf) ? tf : ""}
          onChange={handleMinuteSelect}
        >
          <option value="" disabled>
            분봉
          </option>
          {MINUTE_TFS.map((m) => (
            <option key={m} value={m}>
              {MINUTE_LABEL[m]}
            </option>
          ))}
        </select>
        {PERIOD_BUTTONS.map((btn) => (
          <button
            key={btn.value}
            type="button"
            className={`tf-bar__btn${tf === btn.value ? " tf-bar__btn--active" : ""}`}
            aria-pressed={tf === btn.value}
            onClick={() => handleTfChange(btn.value)}
          >
            {btn.label}
          </button>
        ))}
      </div>

      <div className="candle-chart__canvas-wrap">
        <div
          ref={containerRef}
          className="candle-chart__canvas"
          role="img"
          aria-label={`${TF_ARIA_LABEL[tf]} 캔들 차트${
            data ? `, 최근 ${data.items.length}개 봉` : ""
          }`}
        />
        {loading ? (
          <div className="candle-chart__overlay" role="status" aria-live="polite">
            <span className="candle-chart__spinner" aria-hidden="true" />
            <span className="sr-only">차트를 불러오는 중…</span>
          </div>
        ) : null}
        {!loading && overlayMessage ? (
          <div className="candle-chart__overlay candle-chart__overlay--empty" role="status">
            <p>{overlayMessage}</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
