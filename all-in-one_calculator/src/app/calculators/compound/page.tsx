"use client";

import { useCallback, useState, Suspense } from "react";
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
import { CHART_COLORS } from "@/components/calculators/shared/chart-container";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const frequencyLabels: Record<CompoundFrequency, string> = {
  daily: "일 복리",
  monthly: "월 복리",
  yearly: "연 복리",
};

import { ChartTooltip } from "@/components/calculators/shared/chart-tooltip";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CompoundTooltipWrapper({ active, payload, label }: any) {
  if (!active || !payload || payload.length === 0) return null;

  // 전년 대비 증가율 계산 (별도 표시용)
  const chartData = payload[0]?.payload;
  const prevYear = chartData?.prevBalance;
  const total = payload.reduce((acc: number, curr: { value: number | string }) => acc + Number(curr.value), 0);
  const growthRate =
    prevYear && prevYear > 0
      ? (((total - prevYear) / prevYear) * 100).toFixed(1)
      : null;

  return (
    <div className="flex flex-col gap-2">
      <ChartTooltip active={active} payload={payload} label={label} />
      {growthRate && (
        <div className="bg-amber-400/10 border border-amber-400/20 rounded-lg px-2 py-1 flex items-center justify-between backdrop-blur-sm">
          <span className="text-[10px] font-bold text-amber-400 uppercase tracking-tighter">전년 대비</span>
          <span className="text-xs font-black text-amber-400">+{growthRate}%</span>
        </div>
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
  const [savedId, setSavedId] = useState<string | null>(null);

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
  const pins = usePinStore((s) => s.pins);
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
    if (id) {
      addPin({ resultId: id, displayKey: "finalAmount" });
    }
  };

  const pinned = savedId ? pins.some((p) => p.resultId === savedId) : false;

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

            <Card>
              <CardContent className="pt-4 pb-4">
                <Tabs defaultValue="growth">
                  <TabsList className="mb-3">
                    <TabsTrigger value="growth">자산 성장</TabsTrigger>
                    <TabsTrigger value="pie">원금 vs 이자</TabsTrigger>
                  </TabsList>

                  <TabsContent value="growth">
                    <div className="h-[200px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={chartDataWithPrev}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                          <XAxis dataKey="year" tick={{ fontSize: 12 }} stroke="rgba(255,255,255,0.4)" />
                          <YAxis
                            tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
                            tick={{ fontSize: 12 }}
                            stroke="rgba(255,255,255,0.4)"
                          />
                          <Tooltip
                            content={<CompoundTooltipWrapper />}
                            cursor={{ stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1 }}
                          />
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
                      </ResponsiveContainer>
                    </div>
                  </TabsContent>

                  <TabsContent value="pie">
                    <div className="h-[200px] w-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            innerRadius={50}
                            outerRadius={75}
                            dataKey="value"
                            paddingAngle={5}
                            animationBegin={0}
                            animationDuration={1000}
                          >
                            {pieData.map((_, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={index === 0 ? CHART_COLORS.muted : CHART_COLORS.primary}
                                className="stroke-background hover:opacity-80 transition-opacity"
                                strokeWidth={2}
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            content={<ChartTooltip titleSuffix="" />}
                          />
                          <Legend
                            verticalAlign="bottom"
                            height={36}
                            iconType="circle"
                            formatter={(value) => <span className="text-xs font-medium text-muted-foreground">{value}</span>}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">연도별 상세</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-40 overflow-y-auto">
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
