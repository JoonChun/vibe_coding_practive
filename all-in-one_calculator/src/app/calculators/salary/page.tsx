"use client";

import { useCallback, useState, useRef, Suspense } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { NumberInput } from "@/components/ui/number-input";
import { CalculatorLayout } from "@/components/calculators/shared/calculator-layout";
import { ResultCard } from "@/components/calculators/shared/result-card";
import { ChartContainer, CHART_COLORS } from "@/components/calculators/shared/chart-container";
import { useDebouncedCalc } from "@/hooks/use-debounced-calc";
import { useCalculatorStore } from "@/stores/calculator-store";
import { useHistoryStore } from "@/stores/history-store";
import { usePinStore } from "@/stores/pin-store";
import { calculateSalary, type SalaryInput } from "@/lib/calculators/salary";
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

const CHART_PALETTE = [
  CHART_COLORS.primary,
  CHART_COLORS.secondary,
  CHART_COLORS.tertiary,
  CHART_COLORS.quaternary,
  CHART_COLORS.muted,
  "#f87171",
];

export default function SalaryPage() {
  return (
    <Suspense>
      <SalaryPageInner />
    </Suspense>
  );
}

function SalaryPageInner() {
  const [annualSalary, setAnnualSalary] = useState(50_000_000);
  const [dependents, setDependents] = useState(1);
  const [nonTaxableAllowance, setNonTaxableAllowance] = useState(200_000);
  const savedIdRef = useRef<string | null>(null);

  const applyInputs = useCallback((inputs: Record<string, number | string>) => {
    if (inputs.annualSalary != null) setAnnualSalary(Number(inputs.annualSalary));
    if (inputs.dependents != null) setDependents(Number(inputs.dependents));
    if (inputs.nonTaxableAllowance != null) setNonTaxableAllowance(Number(inputs.nonTaxableAllowance));
  }, []);
  useRestore(applyInputs);

  const input: SalaryInput = { annualSalary, dependents, nonTaxableAllowance };

  const calcFn = useCallback((inp: SalaryInput) => calculateSalary(inp), []);
  const { result } = useDebouncedCalc(calcFn, input);

  const setResult = useCalculatorStore((s) => s.setResult);
  const addToHistory = useHistoryStore((s) => s.addToHistory);
  const { addPin, removePin, isPinned } = usePinStore();

  const saveResult = () => {
    if (!result) return null;
    const id = generateId();
    const calcResult = {
      id,
      type: "salary" as const,
      label: `연봉 ${formatCurrency(annualSalary)} → 월 ${formatCurrency(result.monthlyNet)}`,
      inputs: { annualSalary, dependents, nonTaxableAllowance },
      outputs: {
        monthlyNet: result.monthlyNet,
        annualNet: result.annualNet,
        totalMonthlyDeduction: result.totalMonthlyDeduction,
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
      addPin({ resultId: id, displayKey: "monthlyNet" });
    }
  };

  const pinned = savedIdRef.current ? isPinned(savedIdRef.current) : false;

  const chartData = result
    ? result.deductions.map((d) => ({
        name: d.name,
        금액: d.monthlyAmount,
      }))
    : [];

  return (
    <CalculatorLayout
      title="연봉 실수령액 계산기"
      description="연봉에서 4대 보험과 세금을 공제한 실수령액을 계산합니다."
      inputSlot={
        <Card>
          <CardContent className="pt-6 space-y-5">
            <div className="space-y-2">
              <Label>연봉 (세전)</Label>
              <NumberInput value={annualSalary} onChange={setAnnualSalary} min={0} />
              <Slider
                value={[annualSalary]}
                onValueChange={(v) => setAnnualSalary(v[0])}
                min={20_000_000}
                max={300_000_000}
                step={1_000_000}
              />
            </div>

            <div className="space-y-2">
              <Label>부양가족 수 (본인 포함)</Label>
              <NumberInput value={dependents} onChange={setDependents} min={1} max={20} />
              <Slider
                value={[dependents]}
                onValueChange={(v) => setDependents(v[0])}
                min={1}
                max={10}
                step={1}
              />
            </div>

            <div className="space-y-2">
              <Label>비과세 수당 (월)</Label>
              <NumberInput value={nonTaxableAllowance} onChange={setNonTaxableAllowance} min={0} />
              <Slider
                value={[nonTaxableAllowance]}
                onValueChange={(v) => setNonTaxableAllowance(v[0])}
                min={0}
                max={1_000_000}
                step={10_000}
              />
            </div>
          </CardContent>
        </Card>
      }
      resultSlot={
        result ? (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <ResultCard
                label="월 실수령액"
                value={result.monthlyNet}
                format={formatCurrency}
                isPinned={pinned}
                onTogglePin={handleTogglePin}
              />
              <ResultCard
                label="연 실수령액"
                value={result.annualNet}
                format={formatCurrency}
              />
              <ResultCard
                label="월 공제 합계"
                value={result.totalMonthlyDeduction}
                format={formatCurrency}
              />
            </div>

            <ChartContainer title="공제 항목별 금액 (월)" height={250}>
              <BarChart data={chartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis
                  type="number"
                  tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
                  tick={{ fontSize: 12 }}
                  stroke="rgba(255,255,255,0.4)"
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 12 }}
                  stroke="rgba(255,255,255,0.4)"
                  width={80}
                />
                <Tooltip
                  formatter={(value) => formatCurrency(Number(value))}
                  contentStyle={{ backgroundColor: "#1e293b", border: "none", borderRadius: 8 }}
                />
                <Bar dataKey="금액" radius={[0, 4, 4, 0]}>
                  {chartData.map((_, index) => (
                    <Cell key={index} fill={CHART_PALETTE[index % CHART_PALETTE.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ChartContainer>

            <Card>
              <CardContent className="pt-4">
                <h3 className="text-sm font-medium mb-3">공제 상세 내역</h3>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>항목</TableHead>
                      <TableHead className="text-right">월</TableHead>
                      <TableHead className="text-right">연</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {result.deductions.map((d) => (
                      <TableRow key={d.name}>
                        <TableCell>{d.name}</TableCell>
                        <TableCell className="text-right font-mono">
                          {formatNumber(d.monthlyAmount)}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {formatNumber(d.annualAmount)}
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow className="font-bold">
                      <TableCell>합계</TableCell>
                      <TableCell className="text-right font-mono">
                        {formatNumber(result.totalMonthlyDeduction)}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {formatNumber(result.totalMonthlyDeduction * 12)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </>
        ) : null
      }
    />
  );
}
