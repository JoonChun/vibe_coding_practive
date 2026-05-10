"use client";

import { useCallback, useState, Suspense } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { NumberInput } from "@/components/ui/number-input";
import { Badge } from "@/components/ui/badge";
import { CalculatorLayout } from "@/components/calculators/shared/calculator-layout";
import { ResultCard } from "@/components/calculators/shared/result-card";
import { useDebouncedCalc } from "@/hooks/use-debounced-calc";
import { useCalculatorStore } from "@/stores/calculator-store";
import { useHistoryStore } from "@/stores/history-store";
import { usePinStore } from "@/stores/pin-store";
import { calculateBmi, type BmiInput, type BmiCategory } from "@/lib/calculators/bmi";
import { generateId } from "@/lib/utils";
import { useRestore } from "@/hooks/use-restore";
import { cn } from "@/lib/utils";

// 분류 배지 색상
const categoryBadgeClass: Record<BmiCategory, string> = {
  underweight: "bg-blue-500/10 text-blue-500 border-blue-500/30",
  normal: "bg-emerald-500/10 text-emerald-500 border-emerald-500/30",
  overweight: "bg-amber-500/10 text-amber-500 border-amber-500/30",
  obese1: "bg-orange-500/10 text-orange-500 border-orange-500/30",
  obese2: "bg-red-500/10 text-red-500 border-red-500/30",
  obese3: "bg-rose-600/10 text-rose-600 border-rose-600/30",
};

// 게이지 색상 (구간별)
const gaugeSections = [
  { label: "저체중", from: 0, to: 18.5, color: "bg-blue-400" },
  { label: "정상", from: 18.5, to: 23, color: "bg-emerald-400" },
  { label: "과체중", from: 23, to: 25, color: "bg-amber-400" },
  { label: "비만1", from: 25, to: 30, color: "bg-orange-400" },
  { label: "비만2", from: 30, to: 35, color: "bg-red-400" },
  { label: "고도비만", from: 35, to: 40, color: "bg-rose-600" },
];

const GAUGE_MIN = 0;
const GAUGE_MAX = 40;

function toPercent(bmi: number): number {
  return Math.min(Math.max(((bmi - GAUGE_MIN) / (GAUGE_MAX - GAUGE_MIN)) * 100, 0), 100);
}

interface BmiGaugeProps {
  bmi: number;
}

function BmiGauge({ bmi }: BmiGaugeProps) {
  const indicators = [18.5, 23, 25, 30, 35];

  return (
    <div className="space-y-2">
      <div className="relative h-5 w-full rounded-full overflow-hidden flex">
        {gaugeSections.map((s) => {
          const width = ((s.to - s.from) / (GAUGE_MAX - GAUGE_MIN)) * 100;
          return (
            <div
              key={s.label}
              className={cn("h-full", s.color)}
              style={{ width: `${width}%` }}
            />
          );
        })}
        {/* 현재 BMI 인디케이터 */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg"
          style={{ left: `${toPercent(bmi)}%`, transform: "translateX(-50%)" }}
        >
          <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-white border-2 border-gray-700 shadow" />
        </div>
      </div>

      {/* 경계 마커 */}
      <div className="relative h-4 w-full">
        {indicators.map((v) => (
          <div
            key={v}
            className="absolute flex flex-col items-center"
            style={{ left: `${toPercent(v)}%`, transform: "translateX(-50%)" }}
          >
            <div className="w-px h-2 bg-muted-foreground/40" />
            <span className="text-[9px] text-muted-foreground leading-none">{v}</span>
          </div>
        ))}
      </div>

      {/* 구간 레이블 */}
      <div className="flex w-full text-[9px] text-muted-foreground">
        {gaugeSections.map((s) => {
          const width = ((s.to - s.from) / (GAUGE_MAX - GAUGE_MIN)) * 100;
          return (
            <div
              key={s.label}
              className="text-center truncate"
              style={{ width: `${width}%` }}
            >
              {s.label}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function BmiPage() {
  return (
    <Suspense>
      <BmiPageInner />
    </Suspense>
  );
}

function BmiPageInner() {
  const [heightCm, setHeightCm] = useState(170);
  const [weightKg, setWeightKg] = useState(65);
  const [savedId, setSavedId] = useState<string | null>(null);

  const applyInputs = useCallback((inputs: Record<string, number | string>) => {
    if (inputs.heightCm != null) setHeightCm(Number(inputs.heightCm));
    if (inputs.weightKg != null) setWeightKg(Number(inputs.weightKg));
  }, []);
  useRestore(applyInputs);

  const input: BmiInput = { heightCm, weightKg };

  const calcFn = useCallback((inp: BmiInput) => calculateBmi(inp), []);
  const { result } = useDebouncedCalc(calcFn, input);

  const setResult = useCalculatorStore((s) => s.setResult);
  const addToHistory = useHistoryStore((s) => s.addToHistory);
  const pins = usePinStore((s) => s.pins);
  const { addPin, removePin, isPinned } = usePinStore();

  const saveResult = () => {
    if (!result) return null;
    const id = generateId();
    // BMI 소수점 표시: ×10 정수로 저장, 표시 시 ÷10
    const calcResult = {
      id,
      type: "bmi" as const,
      label: `BMI ${result.bmi.toFixed(1)} (${result.categoryLabel})`,
      inputs: { heightCm, weightKg },
      outputs: {
        bmi: Math.round(result.bmi * 10), // ×10 정수
        standardWeight: result.standardWeight,
        normalRange: `${result.normalMin.toFixed(1)} ~ ${result.normalMax.toFixed(1)} kg`,
      },
      timestamp: Date.now(),
    };
    setResult(calcResult);
    addToHistory(calcResult);
    setSavedId(id);
    return id;
  };

  const handleTogglePin = () => {
    if (savedId && isPinned(savedId)) {
      removePin(savedId);
      setSavedId(null);
      return;
    }
    const id = saveResult();
    if (id) addPin({ resultId: id, displayKey: "bmi" });
  };

  const pinned = savedId ? pins.some((p) => p.resultId === savedId) : false;

  return (
    <CalculatorLayout
      title="BMI 계산기"
      description="체질량지수(BMI)와 표준체중, 정상 체중 범위를 계산합니다."
      inputSlot={
        <Card>
          <CardContent className="pt-6 space-y-5">
            <div className="space-y-2">
              <Label>키 (cm)</Label>
              <NumberInput
                value={heightCm}
                onChange={setHeightCm}
                min={100}
                max={250}
              />
              <Slider
                value={[heightCm]}
                onValueChange={(v) => setHeightCm(v[0])}
                min={100}
                max={250}
                step={1}
              />
            </div>

            <div className="space-y-2">
              <Label>체중 (kg)</Label>
              <NumberInput
                value={weightKg}
                onChange={setWeightKg}
                min={20}
                max={200}
              />
              <Slider
                value={[weightKg]}
                onValueChange={(v) => setWeightKg(v[0])}
                min={20}
                max={200}
                step={0.5}
              />
            </div>
          </CardContent>
        </Card>
      }
      resultSlot={
        result ? (
          <>
            {/* 분류 배지 */}
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={cn(
                  "text-sm px-3 py-1 font-semibold",
                  categoryBadgeClass[result.category]
                )}
              >
                {result.categoryLabel}
              </Badge>
            </div>

            {/* 결과 카드 3개 */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ResultCard
                label="BMI"
                value={Math.round(result.bmi * 10)}
                format={(v) => (v / 10).toFixed(1)}
                isPinned={pinned}
                onTogglePin={handleTogglePin}
              />
              <ResultCard
                label="표준체중"
                value={result.standardWeight}
                format={(v) => `${(Math.round(v * 10) / 10).toFixed(1)} kg`}
              />
              <ResultCard
                label="정상 범위"
                value={0}
                format={() =>
                  `${result.normalMin.toFixed(1)} ~ ${result.normalMax.toFixed(1)} kg`
                }
              />
            </div>

            {/* 게이지 시각화 */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">BMI 범위</CardTitle>
              </CardHeader>
              <CardContent className="pb-5">
                <BmiGauge bmi={result.bmi} />
                <p className="mt-3 text-center text-sm font-bold">
                  현재 BMI:{" "}
                  <span className="font-mono">{result.bmi.toFixed(1)}</span>
                </p>
              </CardContent>
            </Card>
          </>
        ) : null
      }
    />
  );
}
