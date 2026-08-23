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
import type { CandleItem, CandlesResponse, Timeframe } from "../types";
import { SourceBadge } from "./SourceBadge";

interface CandleChartProps {
  code: string;
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

// tf별 초기 요청 개수 — 백엔드 계약(count 최대: 1d/1w/60m/120m/240m는 1000, 그 외 300)에
// 맞춰 "과거 데이터가 안 보인다"는 문제를 근본적으로 없앨 만큼 충분히 깊게 조회한다.
// 더 먼 과거는 차트를 왼쪽으로 스크롤하면 before 커서로 이어서 로딩된다(무한 스크롤).
const COUNT_MAP: Record<Timeframe, number> = {
  "1m": 390, // 정규장 하루치(09:00~15:30 ≈ 390분) — 그 이상은 1분봉 특성상 무의미
  "5m": 300, // yfinance 원천 한계(최근 60일 이하)에서 뽑을 수 있는 사실상 최대
  "15m": 300, // 위와 동일 — 60일 한계
  "30m": 300, // 위와 동일 — 60일 한계
  "60m": 1000, // 백엔드가 yfinance 730일까지 확장 — 60분봉 기준 약 1000봉 커버
  "120m": 500, // 730일 한계 내에서 120분 간격으로 환산한 봉 수
  "240m": 300, // 730일 한계 내에서 240분 간격으로 환산한 봉 수
  "1d": 1000, // 일봉 1000개 ≈ 4년 — 그 이전은 왼쪽 스크롤로 이어서 로딩
  "1w": 1000, // 주봉 1000개 ≈ 19년
  "1M": 300, // 월봉 300개 ≈ 25년
  "1y": 50, // 년봉은 종목 상장 이력을 다 담아도 50개면 충분
};

// 왼쪽 스크롤 시 한 번에 이어 붙이는 과거 페이지 크기(before 커서 요청의 count).
const OLDER_PAGE_COUNT = 300;

// 보이는 범위의 왼쪽 끝이 데이터 시작에서 이 봉수 이내로 접근하면 과거 페이지를 로딩한다.
const LOAD_OLDER_THRESHOLD_BARS = 12;

const MA_CONFIG = [
  { period: 5, color: "#16a34a", label: "MA5" },
  { period: 20, color: "#dc2626", label: "MA20" },
  { period: 60, color: "#f59e0b", label: "MA60" },
  { period: 120, color: "#8b5cf6", label: "MA120" },
] as const;

function isMinuteTf(tf: Timeframe): boolean {
  return (MINUTE_TFS as readonly string[]).includes(tf);
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
export function CandleChart({ code }: CandleChartProps) {
  const [tf, setTf] = useState<Timeframe>("1d");
  const [data, setData] = useState<CandlesResponse | null>(null);
  // 초기 응답 + 왼쪽 스크롤로 이어 붙인 과거 페이지들을 병합한 전체 봉 목록(t 오름차순).
  const [bars, setBars] = useState<CandleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maSeriesRef = useRef<Partial<Record<number, ISeriesApi<"Line">>>>({});
  const requestIdRef = useRef(0);
  // 과거 페이지 로딩 상태 — 렌더와 무관한 진행 플래그라 ref 로 둔다.
  // exhausted: 서버가 더 과거를 못 주는 상태(빈 응답) — tf/code 바뀔 때까지 재요청 안 함.
  const olderRef = useRef({ loading: false, exhausted: false });
  const barsRef = useRef<CandleItem[]>([]);
  // 초기 로딩 직후에만 fitContent — 과거 페이지를 이어 붙일 때 fit 하면 화면이 튄다.
  const initialFitRef = useRef(false);
  // 차트 생성 시 1회 등록하는 스크롤 구독이 항상 최신 상태를 보도록 함수 자체를 ref 로 전달.
  const loadOlderRef = useRef<(() => void) | null>(null);

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
      // 한국 표기 관행: 날짜는 년-월-일 순 — 기본 로케일(일-월-년, 예: "17 Jul '25")을
      // ko-KR + yyyy-MM-dd로 교체(크로스헤어 날짜 라벨·시간축 눈금 모두 적용).
      localization: { locale: "ko-KR", dateFormat: "yyyy-MM-dd" },
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

    // 왼쪽(과거) 스크롤 감지 — 보이는 범위의 시작 인덱스가 데이터 앞머리에 가까워지면
    // 과거 페이지를 이어서 로딩한다. 구독은 차트 수명 1회, 실제 로직은 loadOlderRef 로
    // 위임해 최신 code/tf/bars 상태를 보게 한다.
    chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (!range) return;
      if (range.from > LOAD_OLDER_THRESHOLD_BARS) return;
      loadOlderRef.current?.();
    });

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
    olderRef.current = { loading: false, exhausted: false };

    if (!code) {
      setData(null);
      setBars([]);
      setLoading(false);
      setErrorMessage(null);
      return;
    }

    const requestId = (requestIdRef.current += 1);
    setLoading(true);
    setErrorMessage(null);

    getCandles(code, tf, COUNT_MAP[tf])
      .then((res) => {
        if (requestIdRef.current !== requestId) return;
        setData(res);
        setBars(res.items ?? []);
        initialFitRef.current = true;
        setLoading(false);
      })
      .catch(() => {
        if (requestIdRef.current !== requestId) return;
        setErrorMessage("차트 데이터를 불러오지 못했습니다.");
        setLoading(false);
      });
  }, [code, tf]);

  // 과거 페이지 로더 — 매 렌더마다 최신 클로저로 갱신해 두고, 차트의 스크롤 구독이
  // ref 를 통해 호출한다(구독 자체는 차트 수명 1회 등록).
  loadOlderRef.current = () => {
    const older = olderRef.current;
    if (older.loading || older.exhausted || loading || !code) return;
    const current = barsRef.current;
    if (current.length === 0) return;

    const oldest = current[0].t;
    const requestId = requestIdRef.current; // 초기 재조회가 나가면 이 응답은 버린다
    older.loading = true;

    getCandles(code, tf, OLDER_PAGE_COUNT, oldest)
      .then((res) => {
        if (requestIdRef.current !== requestId) return;
        // 서버가 경계를 지켜도 방어적으로 한 번 더 거른다(중복 t 방지).
        const fresh = (res.items ?? []).filter((item) => item.t < oldest);
        if (fresh.length === 0) {
          older.exhausted = true; // 원천 고갈 — tf/code 바뀔 때까지 재요청 안 함
          return;
        }
        setBars((prev) => [...fresh, ...prev]);
      })
      .catch(() => {
        // 일시 실패 — exhausted 는 세우지 않는다(다음 스크롤에서 재시도).
      })
      .finally(() => {
        older.loading = false;
      });
  };

  // 봉 목록(초기 로딩 또는 과거 페이지 병합)이 바뀌면 캔들/거래량/이동평균 시리즈에 반영.
  useEffect(() => {
    barsRef.current = bars;

    const candleSeries = candleSeriesRef.current;
    const volumeSeries = volumeSeriesRef.current;
    if (!candleSeries || !volumeSeries) return;

    const validBars = bars
      .filter(isValidCandle)
      .slice()
      .sort((a, b) => a.t - b.t);

    const candleData: CandlestickData[] = validBars.map((bar) => ({
      time: bar.t as UTCTimestamp,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));

    const volumeData: HistogramData[] = validBars.map((bar) => ({
      time: bar.t as UTCTimestamp,
      value: bar.volume,
      color: bar.close >= bar.open ? UP_VOLUME_COLOR : DOWN_VOLUME_COLOR,
    }));

    candleSeries.setData(candleData);
    volumeSeries.setData(volumeData);

    for (const ma of MA_CONFIG) {
      maSeriesRef.current[ma.period]?.setData(computeMovingAverage(validBars, ma.period));
    }

    // fitContent 는 초기 로딩 직후 1회만 — 과거 페이지를 이어 붙일 때 fit 하면
    // 보고 있던 구간이 전체 범위로 튀어 스크롤 위치를 잃는다(시간축 기준이라
    // setData 만으로는 보이는 구간이 유지된다).
    if (initialFitRef.current) {
      initialFitRef.current = false;
      chartRef.current?.timeScale().fitContent();
    }
  }, [bars]);

  function handleTfChange(next: Timeframe) {
    if (next === tf) return;
    setTf(next);
  }

  function handleMinuteSelect(e: ChangeEvent<HTMLSelectElement>) {
    const value = e.target.value;
    if (!value) return;
    handleTfChange(value as Timeframe);
  }

  const isEmpty = !loading && data !== null && bars.length === 0;
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
        {data ? <SourceBadge source={data.source} /> : null}
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
