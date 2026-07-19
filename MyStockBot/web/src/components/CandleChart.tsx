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
import { useEffect, useRef, useState, type ChangeEvent, type PointerEvent as ReactPointerEvent } from "react";
import { getCandles } from "../api";
import type { CandleItem, CandlesResponse, LiveBar, Timeframe } from "../types";
import { epochToKstDateStr } from "../utils/format";
import { SourceBadge } from "./SourceBadge";

interface CandleChartProps {
  code: string;
  /** WS bar_update로 갱신되는 이 code의 타임프레임별 진행중(미마감) 봉 — useTickStream().liveBars[code] */
  liveBars?: Partial<Record<Timeframe, LiveBar>>;
  /** tickStream.connected && tickStream.kisConnected — 툴바 LIVE 태그 노출 조건(연결 살아있을 때만) */
  wsConnected?: boolean;
  /** 봉을 짧게 탭했을 때(§7) 그 봉의 날짜(YYYY-MM-DD, KST)를 알려줌 — Phase 3 "그날의 나" 진입점.
   * 미전달 시 탭 판별 로직 자체를 붙이지 않아 기존 크로스헤어/팬/줌 동작에 전혀 영향 없다. */
  onBarTap?: (dateStr: string) => void;
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

// tf별 요청 개수 — 백엔드 계약(count 최대: 1d/1w/60m/120m/240m는 1000, 그 외 300)에 맞춰
// "과거 데이터가 안 보인다"는 문제를 근본적으로 없앨 만큼 충분히 깊게 조회한다.
const COUNT_MAP: Record<Timeframe, number> = {
  "1m": 390, // 정규장 하루치(09:00~15:30 ≈ 390분) — 그 이상은 1분봉 특성상 무의미
  "5m": 300, // yfinance 원천 한계(최근 60일 이하)에서 뽑을 수 있는 사실상 최대
  "15m": 300, // 위와 동일 — 60일 한계
  "30m": 300, // 위와 동일 — 60일 한계
  "60m": 1000, // 백엔드가 yfinance 730일까지 확장 — 60분봉 기준 약 1000봉 커버
  "120m": 500, // 730일 한계 내에서 120분 간격으로 환산한 봉 수
  "240m": 300, // 730일 한계 내에서 240분 간격으로 환산한 봉 수
  "1d": 1000, // 일봉 1000개 ≈ 4년 — "재작년 게 안 보인다" 문제 해소
  "1w": 1000, // 주봉 1000개 ≈ 19년
  "1M": 300, // 월봉 300개 ≈ 25년
  "1y": 50, // 년봉은 종목 상장 이력을 다 담아도 50개면 충분
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

// 봉 탭(§7-1) 지원 tf — 하루 이내(또는 하루 그 자체) 시각을 갖는 봉만 "그 봉의 날짜"가 모호함이
// 없다(1w/1M/1y는 한 봉이 여러 날을 품어 지원하지 않음). 오늘 시점 값은 LIVE_CAPABLE_TFS와
// 우연히 같지만 개념이 다른 규칙(하나는 WS bar_update 수신 가능 여부, 하나는 탭 프리필 가능 여부)
// 이라 별도 상수로 둔다 — 훗날 둘 중 하나만 바뀌어도 서로 영향받지 않도록.
const TAP_SUPPORTED_TFS = new Set<Timeframe>([...MINUTE_TFS, "1d"]);

function isTapSupportedTf(tf: Timeframe): boolean {
  return TAP_SUPPORTED_TFS.has(tf);
}

// 탭/롱프레스/드래그 판별 임계값(§7) — 실측 후 조정 가능한 초안 수치.
// TAP_MAX 는 lightweight-charts 내부 터치 롱프레스(크로스헤어 진입, 약 240ms로 알려짐)보다
// 짧게 잡아 "크로스헤어도 뜨고 탭도 발동"하는 이중 해석 구간을 없앤다(검수 발견).
const TAP_MAX_MS = 220;
const LONG_PRESS_MS = 450;
const MOVE_THRESHOLD_PX = 8;
const TAP_TOAST_DURATION_MS = 2000;
const TAP_UNSUPPORTED_TOAST = '이 주기에서는 지원하지 않아요 — 일봉 이하에서 사용해주세요';

interface TapGestureState {
  pointerId: number;
  x: number;
  y: number;
  startTime: number;
  moved: boolean;
  longPressFired: boolean;
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
export function CandleChart({ code, liveBars, wsConnected = false, onBarTap }: CandleChartProps) {
  const [tf, setTf] = useState<Timeframe>("1d");
  const [data, setData] = useState<CandlesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [tapToast, setTapToast] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const maSeriesRef = useRef<Partial<Record<number, ISeriesApi<"Line">>>>({});
  const requestIdRef = useRef(0);
  const gestureRef = useRef<TapGestureState | null>(null);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tapToastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
      // 원화는 소수점을 쓰지 않으므로 우측 가격축·크로스헤어 라벨에 기본 precision(2)이 남기는
      // ".00" 노출을 제거(거래량 히스토그램은 기존 type: "volume" 포맷 그대로 유지, 영향 없음).
      priceFormat: { type: "price", precision: 0, minMove: 1 },
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
        priceFormat: { type: "price", precision: 0, minMove: 1 },
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

    getCandles(code, tf, COUNT_MAP[tf])
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

  function clearLongPressTimer() {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
  }

  function showTapToast(message: string) {
    setTapToast(message);
    if (tapToastTimerRef.current) clearTimeout(tapToastTimerRef.current);
    tapToastTimerRef.current = setTimeout(() => setTapToast(null), TAP_TOAST_DURATION_MS);
  }

  // 토스트 타이머 정리(언마운트 시) — onBarTap 유무와 무관하게 항상 안전하게 정리.
  useEffect(() => {
    return () => {
      if (tapToastTimerRef.current) clearTimeout(tapToastTimerRef.current);
    };
  }, []);

  // 컨테이너 밖에서 pointerup/cancel이 나면(팬 도중 손가락이 캔버스 밖으로 나가는 등) 우리 쪽
  // 제스처 추적이 미아 상태로 남지 않도록 하는 안전망 — 실제 탭 판정은 하지 않고 상태만 정리한다.
  useEffect(() => {
    if (!onBarTap) return;
    function reset(e: PointerEvent) {
      const state = gestureRef.current;
      if (state && state.pointerId === e.pointerId) {
        gestureRef.current = null;
        clearLongPressTimer();
      }
    }
    window.addEventListener("pointerup", reset);
    window.addEventListener("pointercancel", reset);
    return () => {
      window.removeEventListener("pointerup", reset);
      window.removeEventListener("pointercancel", reset);
    };
  }, [onBarTap]);

  function handleBarTapConfirmed(clientX: number) {
    if (!onBarTap) return;
    if (!isTapSupportedTf(tf)) {
      showTapToast(TAP_UNSUPPORTED_TOAST);
      return;
    }
    const container = containerRef.current;
    const chart = chartRef.current;
    if (!container || !chart) return;
    const rect = container.getBoundingClientRect();
    const x = clientX - rect.left;
    const time = chart.timeScale().coordinateToTime(x);
    if (typeof time !== "number") return; // 데이터 없는 여백을 탭한 경우 등 — 조용히 무시
    onBarTap(epochToKstDateStr(time));
  }

  // 탭 vs 롱프레스 vs 드래그 판별(§7) — 시간(ms)+이동거리(px) 두 축으로만 갈라 애매함을 없앤다.
  // preventDefault/stopPropagation을 전혀 쓰지 않아 lightweight-charts 자체의 크로스헤어·팬·줌은
  // 완전히 그대로 동작한다(이 핸들러들은 그 위에 얹힌 "관찰자"일 뿐).
  function handleCanvasPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    if (gestureRef.current) {
      // 두 번째 손가락 도착 = 핀치 줌 시작 — 기존 탭 후보를 통째로 무효화한다.
      // (무시만 하면 앵커 손가락이 8px 미만 이동 후 릴리즈될 때 탭으로 오발동 — 검수 발견)
      gestureRef.current = null;
      clearLongPressTimer();
      return;
    }
    gestureRef.current = {
      pointerId: e.pointerId,
      x: e.clientX,
      y: e.clientY,
      startTime: performance.now(),
      moved: false,
      longPressFired: false,
    };
    clearLongPressTimer();
    longPressTimerRef.current = setTimeout(() => {
      const state = gestureRef.current;
      if (state && !state.moved) {
        // 크로스헤어 스크럽 진입 — 시각 피드백은 lightweight-charts 자체의 크로스헤어가 담당(§7 "권장").
        state.longPressFired = true;
      }
    }, LONG_PRESS_MS);
  }

  function handleCanvasPointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    const state = gestureRef.current;
    if (!state || state.pointerId !== e.pointerId || state.moved) return;
    const dx = e.clientX - state.x;
    const dy = e.clientY - state.y;
    if (Math.hypot(dx, dy) >= MOVE_THRESHOLD_PX) {
      state.moved = true; // 드래그로 확정 — 이후 팬/줌은 라이브러리 기본 동작에 맡기고 우리는 손 뗀다
      clearLongPressTimer();
    }
  }

  function handleCanvasPointerUp(e: ReactPointerEvent<HTMLDivElement>) {
    const state = gestureRef.current;
    if (!state || state.pointerId !== e.pointerId) return;
    gestureRef.current = null;
    clearLongPressTimer();
    if (state.moved || state.longPressFired) return; // 드래그였거나 이미 롱프레스(스크럽) 해제 — 탭 아님
    const elapsed = performance.now() - state.startTime;
    if (elapsed > TAP_MAX_MS) return; // 탭 창(220ms) 초과 — 크로스헤어 영역이므로 아무 것도 하지 않음
    handleBarTapConfirmed(e.clientX);
  }

  function handleCanvasPointerCancel(e: ReactPointerEvent<HTMLDivElement>) {
    const state = gestureRef.current;
    if (!state || state.pointerId !== e.pointerId) return;
    gestureRef.current = null;
    clearLongPressTimer();
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

      {onBarTap && isTapSupportedTf(tf) ? (
        <p className="candle-chart__tap-hint">
          🕰 봉을 탭하면 &quot;그날의 나&quot;를 볼 수 있어요
        </p>
      ) : null}

      <div className="candle-chart__canvas-wrap">
        <div
          ref={containerRef}
          className="candle-chart__canvas"
          role="img"
          aria-label={`${TF_ARIA_LABEL[tf]} 캔들 차트${
            data ? `, 최근 ${data.items.length}개 봉` : ""
          }`}
          onPointerDown={onBarTap ? handleCanvasPointerDown : undefined}
          onPointerMove={onBarTap ? handleCanvasPointerMove : undefined}
          onPointerUp={onBarTap ? handleCanvasPointerUp : undefined}
          onPointerCancel={onBarTap ? handleCanvasPointerCancel : undefined}
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
        {tapToast ? (
          <div className="candle-chart__toast" role="status" aria-live="polite">
            {tapToast}
          </div>
        ) : null}
      </div>
    </div>
  );
}
