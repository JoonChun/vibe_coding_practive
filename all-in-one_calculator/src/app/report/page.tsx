"use client";

import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Trash2 } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCalculatorStore } from "@/stores/calculator-store";
import { generateComparison } from "@/lib/report-engine";
import { formatCurrency, formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { CalculationResult, CalculatorType } from "@/types/calculator";

const typeLabels: Record<CalculatorType, string> = {
  compound: "복리/적금",
  loan: "대출 상환",
  salary: "연봉 실수령액",
  unit: "단위 변환",
  dday: "디데이",
};

export default function ReportPage() {
  const [mounted, setMounted] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const results = useCalculatorStore((s) => s.results);
  const removeResult = useCalculatorStore((s) => s.removeResult);

  useEffect(() => setMounted(true), []);

  const allResults = useMemo(
    () =>
      Object.values(results).sort((a, b) => b.timestamp - a.timestamp),
    [results]
  );

  const resultsByType = useMemo(() => {
    const grouped: Partial<Record<CalculatorType, CalculationResult[]>> = {};
    for (const r of allResults) {
      if (!grouped[r.type]) grouped[r.type] = [];
      grouped[r.type]!.push(r);
    }
    return grouped;
  }, [allResults]);

  const selectedItems = useMemo(
    () => selected.map((id) => results[id]).filter(Boolean) as CalculationResult[],
    [selected, results]
  );

  const comparison = useMemo(
    () => (selectedItems.length >= 2 ? generateComparison(selectedItems) : null),
    [selectedItems]
  );

  const toggleSelect = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id].slice(-3)
    );
  };

  if (!mounted) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">비교 리포트</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          저장된 계산 결과를 선택하여 비교 분석합니다. (최대 3개)
        </p>
      </div>

      {/* 결과 선택 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            비교할 결과 선택 ({selected.length}/3)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {allResults.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              저장된 계산 결과가 없습니다. 계산기에서 결과를 저장하세요.
            </p>
          ) : (
            <div className="space-y-6">
              {(Object.keys(typeLabels) as CalculatorType[])
                .filter((type) => resultsByType[type]?.length)
                .map((type) => (
                  <div key={type} className="space-y-2">
                    <div className="flex items-center justify-between px-1">
                      <p className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        {typeLabels[type]}
                      </p>
                      <Badge variant="outline" className="text-xs font-normal">
                        {resultsByType[type]!.length}개
                      </Badge>
                    </div>
                    {/* 드래그(가로 스크롤) 영역 */}
                    <div className="flex overflow-x-auto gap-3 pb-4 snap-x snap-mandatory hide-scroll-bar">
                      {resultsByType[type]!.map((r) => (
                        <Card
                          key={r.id}
                          onClick={() => toggleSelect(r.id)}
                          className={cn(
                            "relative min-w-[240px] max-w-[240px] shrink-0 snap-center cursor-pointer transition-all border-2",
                            selected.includes(r.id)
                              ? "border-primary bg-primary/5 shadow-md"
                              : "border-transparent hover:border-border hover:bg-accent/30"
                          )}
                        >
                          <CardContent className="p-4 relative group">
                            <div className="flex justify-between items-start mb-2 gap-2">
                              {selected.includes(r.id) ? (
                                <Badge variant="default" className="text-xs">
                                  시나리오 {String.fromCharCode(65 + selected.indexOf(r.id))}
                                </Badge>
                              ) : (
                                <Badge variant="secondary" className="text-xs group-hover:bg-accent">
                                  선택 가능
                                </Badge>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                className={cn(
                                  "h-7 w-7 transition-opacity",
                                  selected.includes(r.id) 
                                    ? "opacity-100 text-muted-foreground hover:text-destructive" 
                                    : "opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                                )}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  removeResult(r.id);
                                  setSelected((prev) => prev.filter((id) => id !== r.id));
                                }}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                            <p className="text-sm font-medium leading-snug line-clamp-2 mt-1" title={r.label}>
                              {r.label}
                            </p>
                            <p className="text-xs text-muted-foreground mt-3">
                              {new Date(r.timestamp).toLocaleString("ko-KR")}
                            </p>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 비교 결과 */}
      {comparison && (
        <>
          {comparison.insight && (
            <Card className="border-primary/50 bg-primary/5">
              <CardContent className="py-4">
                <p className="text-sm font-medium text-primary">
                  {comparison.insight}
                </p>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">비교 테이블</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>항목</TableHead>
                    {comparison.items.map((item, i) => (
                      <TableHead key={item.id} className="text-right">
                        시나리오 {String.fromCharCode(65 + i)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className="text-muted-foreground">이름</TableCell>
                    {comparison.items.map((item) => (
                      <TableCell key={item.id} className="text-right text-xs">
                        {item.label}
                      </TableCell>
                    ))}
                  </TableRow>
                  {comparison.fields.map((field) => (
                    <TableRow key={field.field}>
                      <TableCell>{field.label}</TableCell>
                      {field.values.map((value, i) => (
                        <TableCell
                          key={i}
                          className={cn(
                            "text-right font-mono",
                            field.winnerIndex === i && "text-primary font-bold"
                          )}
                        >
                          {typeof value === "number"
                            ? formatCurrency(value)
                            : value}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
