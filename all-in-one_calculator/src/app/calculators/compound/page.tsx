"use client";

import { useCallback, useState, useRef, Suspense } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  ResponsiveContainer,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { NumberInput } from "@/components/ui/number-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CalculatorLayout } from "@/components/calculators/shared/calculator-layout";
import { ResultCard } from "@/components/calculators/shared/result-card";
import { ChartContainer, CHART_COLORS } from "@/components/calculators/shared/chart-container";
import { useDebouncedCalc } from "@/hooks/use-debounced-calc";
import { useCalculatorStore } from "@/stores/calculator-store";
import { useHistoryStore } from "@/stores/history-store";
import { usePinStore } from "@/stores/pin-store";
import {
  calculateCompound,
  type CompoundInput,
  type CompoundFrequency,
} from "@/lib/calculators/compound";
import { formatCurrency, formatNumber, generateId } from "@/lib/utils";
import { useRestore } from "@/hooks/use-restore";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const frequencyLabels: Record<CompoundFrequency, string> = {
  daily: "일 복리",
  monthly: "월 복리",
  yearly: "연 복리",
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CompoundTooltip({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;

  const deposit = payload.find((p: any) => p.dataKey === "totalDeposit")?.value ?? 0;
  const interest = payload.find((p: any) => p.dataKey === "totalInterest")?.value ?? 0;
  const total = Number(deposit) + Number(interest);

  // 전년 대비 증가율 계산 (payload에서 yearlyBreakdown 참조)
  const chartData = payload[0]?.payload;
  const prevYear = chartData?.prevBalance;
  const growthRate =
    prevYear && prevYear > 0
      ? (((total - prevYear) / prevYear) * 100).toFixed(1)
      : null;

  return (
    <div className="rounded-lg bg-slate-800 px-3 py-2 text-xs shadow-lg border border-white/10">
      <p className="font-medium text-white mb-1">{label}년차</p>
      <p className="text-emerald-400">총 자산: {formatCurrency(total)}</p>
      <p className="text-slate-300">적립금: {formatCurrency(Number(deposit))}</p>
      <p className="text-slate-300">이자: {formatCurrency(Number(interest))}</p>
      {growthRate && (
        <p className="text-amber-400 mt-1">전년 대비: +{growthRate}%</p>
      )}
    </div>
  );
}

export default function CompoundPage() {
  return (
    <Suspense>
      <CompoundPageInner />
    </Suspense>
  );
}

function CompoundPageInner() {
  const [principal, setPrincipal] = useState(10_000_000);
  const [monthlyContribution, setMonthlyContribution] = useState(500_000);
  const [annualRate, setAnnualRate] = useState(5);
  const [years, setYears] = useState(10);
  const [frequency, setFrequency] = useState<CompoundFrequency>("monthly");
  const savedIdRef = useRef<string | null>(null);

  const applyInputs = useCallback((inputs: Record<string, number | string>) => {
    if (inputs.principal != null) setPrincipal(Number(inputs.principal));
    if (inputs.monthlyContribution != null) setMonthlyContribution(Number(inputs.monthlyContribution));
    if (inputs.annualRate != null) setAnnualRate(Number(inputs.annualRate));
    if (inputs.years != null) setYears(Number(inputs.years));
    if (inputs.frequency != null) setFrequency(inputs.frequency as CompoundFrequency);
  }, []);
  useRestore(applyInputs);

  const input: CompoundInput = {
    principal,
    monthlyContribution,
    annualRate,
    years,
    frequency,
  };

  const calcFn = useCallback(
    (inp: CompoundInput) => calculateCompound(inp),
    []
  );
  const { result } = useDebouncedCalc(calcFn, input);

  const setResult = useCalculatorStore((s) => s.setResult);
  const addToHistory = useHistoryStore((s) => s.addToHistory);
  const { addPin, removePin, isPinned } = usePinStore();

  const saveResult = () => {
    if (!result) return null;
    const id = generateId();
    const calcResult = {
      id,
      type: "compound" as const,
      label: `복리 ${formatCurrency(result.finalAmount)}`,
      inputs: { principal, monthlyContribution, annualRate, years, frequency },
      outputs: {
        finalAmount: result.finalAmount,
        totalDeposit: result.totalDeposit,
        totalInterest: result.totalInterest,
      },
      timestamp: Date.now(),
    };
    setResult(calcResult);
    addToHistory(calcResult);
    savedIdRef.current = id;
    return id;
  };

  const handleTogglePin = () => {
    if (savedIdRef.current && isPinned(savedIdRef.current)) {
      removePin(savedIdRef.current);
      savedIdRef.current = null;
      return;
    }
    const id = saveResult();
    if (id) {
      addPin({ resultId: id, displayKey: "finalAmount" });
    }
  };

  const pinned = savedIdRef.current ? isPinned(savedIdRef.current) : false;

  const pieData = result
    ? [
        { name: "원금 + 적립", value: result.totalDeposit },
        { name: "이자 수익", value: result.totalInterest },
      ]
    : [];

  // 차트 데이터에 전년도 잔액 추가 (커스텀 툴팁용)
  const chartDataWithPrev = result
    ? result.yearlyBreakdown.map((row, i) => ({
        ...row,
        prevBalance:
          i > 0
            ? result.yearlyBreakdown[i - 1].balance
            : input.principal,
      }))
    : [];

  return (
    <CalculatorLayout
      title="복리/적금 계산기"
      description="원금과 월 적립액에 대한 복리 수익을 시뮬레이션합니다."
      inputSlot={
        <Card>
          <CardContent className="pt-6 space-y-5">
            <div className="space-y-2">
              <Label>원금</Label>
              <NumberInput value={principal} onChange={setPrincipal} min={0} />
              <Slider
                value={[principal]}
                onValueChange={(v) => setPrincipal(v[0])}
                min={0}
                max={1_000_000_000}
                step={1_000_000}
              />
            </div>

            <div className="space-y-2">
              <Label>월 적립액</Label>
              <NumberInput value={monthlyContribution} onChange={setMonthlyContribution} min={0} />
              <Slider
                value={[monthlyContribution]}
                onValueChange={(v) => setMonthlyContribution(v[0])}
                min={0}
                max={10_000_000}
                step={100_000}
              />
            </div>

            <div className="space-y-2">
              <Label>연이율 (%)</Label>
              <NumberInput value={annualRate} onChange={setAnnualRate} min={0} max={30} />
              <Slider
                value={[annualRate]}
                onValueChange={(v) => setAnnualRate(v[0])}
                min={0}
                max={30}
                step={0.1}
              />
            </div>

            <div className="space-y-2">
              <Label>기간 (년)</Label>
              <NumberInput value={years} onChange={setYears} min={1} max={50} />
              <Slider
                value={[years]}
                onValueChange={(v) => setYears(v[0])}
                min={1}
                max={50}
                step={1}
              />
            </div>

            <div className="space-y-2">
              <Label>복리 주기</Label>
              <Select value={frequency} onValueChange={(v) => setFrequency(v as CompoundFrequency)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(frequencyLabels).map(([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      }
      resultSlot={
        result ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ResultCard
                label="최종 금액"
                value={result.finalAmount}
                format={formatCurrency}
                isPinned={pinned}
                onTogglePin={handleTogglePin}
              />
              <ResultCard
                label="총 적립액"
                value={result.totalDeposit}
                format={formatCurrency}
              />
              <ResultCard
                label="이자 수익"
                value={result.totalInterest}
                format={formatCurrency}
              />
            </div>

            <ChartContainer title="자산 성장 추이">
              <AreaChart data={chartDataWithPrev}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="year" tick={{ fontSize: 12 }} stroke="rgba(255,255,255,0.4)" />
                <YAxis
                  tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
                  tick={{ fontSize: 12 }}
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip content={<CompoundTooltip />} />
                <Area
                  type="monotone"
                  dataKey="totalDeposit"
                  stackId="1"
                  fill={CHART_COLORS.muted}
                  stroke={CHART_COLORS.muted}
                  name="적립금"
                />
                <Area
                  type="monotone"
                  dataKey="totalInterest"
                  stackId="1"
                  fill={CHART_COLORS.primary}
                  stroke={CHART_COLORS.primary}
                  name="이자"
                />
              </AreaChart>
            </ChartContainer>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">원금 vs 이자</CardTitle>
              </CardHeader>
              <CardContent className="pb-4">
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="45%"
                      innerRadius={55}
                      outerRadius={85}
                      dataKey="value"
                      paddingAngle={2}
                      isAnimationActive={false}
                    >
                      <Cell fill={CHART_COLORS.muted} />
                      <Cell fill={CHART_COLORS.primary} />
                    </Pie>
                    <Legend />
                    <Tooltip
                      formatter={(value) => formatCurrency(Number(value))}
                      contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: 8 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">연도별 상세</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-60 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>연도</TableHead>
                        <TableHead className="text-right">잔액</TableHead>
                        <TableHead className="text-right">적립금</TableHead>
                        <TableHead className="text-right">이자</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.yearlyBreakdown.map((row) => (
                        <TableRow key={row.year}>
                          <TableCell>{row.year}년</TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.balance)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.totalDeposit)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.totalInterest)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </>
        ) : null
      }
    />
  );
}
