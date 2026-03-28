"use client";

import { useCallback, useState, useRef, Suspense } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
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
  calculateLoan,
  type LoanInput,
  type RepaymentMethod,
} from "@/lib/calculators/loan";
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

const methodLabels: Record<RepaymentMethod, string> = {
  "equal-payment": "원리금균등",
  "equal-principal": "원금균등",
  bullet: "만기일시",
};

import { ChartTooltip } from "@/components/calculators/shared/chart-tooltip";

export default function LoanPage() {
  return (
    <Suspense>
      <LoanPageInner />
    </Suspense>
  );
}

function LoanPageInner() {
  const [loanAmount, setLoanAmount] = useState(300_000_000);
  const [annualRate, setAnnualRate] = useState(3.5);
  const [termYears, setTermYears] = useState(30);
  const [method, setMethod] = useState<RepaymentMethod>("equal-payment");
  const savedIdRef = useRef<string | null>(null);

  const applyInputs = useCallback((inputs: Record<string, number | string>) => {
    if (inputs.loanAmount != null) setLoanAmount(Number(inputs.loanAmount));
    if (inputs.annualRate != null) setAnnualRate(Number(inputs.annualRate));
    if (inputs.termMonths != null) setTermYears(Math.round(Number(inputs.termMonths) / 12));
    if (inputs.method != null) setMethod(inputs.method as RepaymentMethod);
  }, []);
  useRestore(applyInputs);

  const input: LoanInput = {
    loanAmount,
    annualRate,
    termMonths: termYears * 12,
    method,
  };

  const calcFn = useCallback((inp: LoanInput) => calculateLoan(inp), []);
  const { result } = useDebouncedCalc(calcFn, input);

  const setResult = useCalculatorStore((s) => s.setResult);
  const addToHistory = useHistoryStore((s) => s.addToHistory);
  const { addPin, removePin, isPinned } = usePinStore();

  const saveResult = () => {
    if (!result) return null;
    const id = generateId();
    const calcResult = {
      id,
      type: "loan" as const,
      label: `대출 ${methodLabels[method]} ${formatCurrency(result.monthlyPayment)}/월`,
      inputs: { loanAmount, annualRate, termMonths: termYears * 12, method },
      outputs: {
        monthlyPayment: result.monthlyPayment,
        totalPayment: result.totalPayment,
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
      addPin({ resultId: id, displayKey: "monthlyPayment" });
    }
  };

  const pinned = savedIdRef.current ? isPinned(savedIdRef.current) : false;

  const chartData = result
    ? result.schedule
        .filter((_, i) => i % 12 === 11 || i === 0)
        .map((row) => ({
          year: Math.ceil(row.month / 12),
          원금: row.principal,
          이자: row.interest,
        }))
    : [];

  return (
    <CalculatorLayout
      title="대출 상환 계산기"
      description="대출 상환 방식별 월 상환액과 총이자를 비교합니다."
      inputSlot={
        <Card>
          <CardContent className="pt-6 space-y-5">
            <div className="space-y-2">
              <Label>대출 금액</Label>
              <NumberInput value={loanAmount} onChange={setLoanAmount} min={0} />
              <Slider
                value={[loanAmount]}
                onValueChange={(v) => setLoanAmount(v[0])}
                min={10_000_000}
                max={1_000_000_000}
                step={10_000_000}
              />
            </div>

            <div className="space-y-2">
              <Label>연이율 (%)</Label>
              <NumberInput value={annualRate} onChange={setAnnualRate} min={0} max={20} />
              <Slider
                value={[annualRate]}
                onValueChange={(v) => setAnnualRate(v[0])}
                min={0.1}
                max={20}
                step={0.1}
              />
            </div>

            <div className="space-y-2">
              <Label>대출 기간 (년)</Label>
              <NumberInput value={termYears} onChange={setTermYears} min={1} max={40} />
              <Slider
                value={[termYears]}
                onValueChange={(v) => setTermYears(v[0])}
                min={1}
                max={40}
                step={1}
              />
            </div>

            <div className="space-y-2">
              <Label>상환 방식</Label>
              <Select value={method} onValueChange={(v) => setMethod(v as RepaymentMethod)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(methodLabels).map(([key, label]) => (
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
                label={method === "equal-principal" ? "첫 달 상환액" : "월 상환액"}
                value={result.monthlyPayment}
                format={formatCurrency}
                isPinned={pinned}
                onTogglePin={handleTogglePin}
              />
              <ResultCard
                label="총 상환액"
                value={result.totalPayment}
                format={formatCurrency}
              />
              <ResultCard
                label="총 이자"
                value={result.totalInterest}
                format={formatCurrency}
              />
            </div>

            <ChartContainer title="연도별 원금/이자 비중">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                <XAxis dataKey="year" tick={{ fontSize: 12 }} stroke="rgba(255,255,255,0.4)" />
                <YAxis
                  tickFormatter={(v) => `${(v / 10000).toFixed(0)}만`}
                  tick={{ fontSize: 12 }}
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip 
                  content={<ChartTooltip />} 
                  cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                />
                <Legend />
                <Bar dataKey="원금" fill={CHART_COLORS.primary} stackId="a" />
                <Bar dataKey="이자" fill={CHART_COLORS.muted} stackId="a" />
              </BarChart>
            </ChartContainer>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">상환 스케줄</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-60 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>회차</TableHead>
                        <TableHead className="text-right">상환액</TableHead>
                        <TableHead className="text-right">원금</TableHead>
                        <TableHead className="text-right">이자</TableHead>
                        <TableHead className="text-right">잔액</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.schedule.slice(0, 60).map((row) => (
                        <TableRow key={row.month}>
                          <TableCell>{row.month}개월</TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.payment)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.principal)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.interest)}
                          </TableCell>
                          <TableCell className="text-right font-mono">
                            {formatNumber(row.remainingBalance)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {result.schedule.length > 60 && (
                    <p className="text-xs text-muted-foreground text-center mt-2">
                      처음 60개월만 표시됩니다. (전체 {result.schedule.length}개월)
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </>
        ) : null
      }
    />
  );
}
