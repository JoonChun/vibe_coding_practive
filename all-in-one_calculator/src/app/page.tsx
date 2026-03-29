"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  TrendingUp,
  Landmark,
  Wallet,
  ArrowLeftRight,
  Calendar,
  PinOff,
  Trash2,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePinStore } from "@/stores/pin-store";
import { useCalculatorStore } from "@/stores/calculator-store";
import { useHistoryStore } from "@/stores/history-store";
import { formatCurrency, formatNumber } from "@/lib/utils";
import type { CalculatorType, CALCULATOR_LABELS } from "@/types/calculator";

const typeIcons: Record<CalculatorType, typeof TrendingUp> = {
  compound: TrendingUp,
  loan: Landmark,
  salary: Wallet,
  unit: ArrowLeftRight,
  dday: Calendar,
};

const typeLabels: Record<CalculatorType, string> = {
  compound: "복리/적금",
  loan: "대출 상환",
  salary: "연봉 실수령액",
  unit: "단위 변환",
  dday: "디데이",
};

const typeLinks: Record<CalculatorType, string> = {
  compound: "/calculators/compound",
  loan: "/calculators/loan",
  salary: "/calculators/salary",
  unit: "/calculators/unit",
  dday: "/calculators/dday",
};

export default function Dashboard() {
  const [mounted, setMounted] = useState(false);
  const pins = usePinStore((s) => s.pins);
  const removePin = usePinStore((s) => s.removePin);
  const results = useCalculatorStore((s) => s.results);
  const history = useHistoryStore((s) => s.history);
  const removeFromHistory = useHistoryStore((s) => s.removeFromHistory);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold">대시보드</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          핀 고정된 지표와 최근 계산 내역을 한눈에 확인하세요.
        </p>
      </div>

      {/* 핀 위젯 */}
      <section>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">
          핀 위젯 ({pins.length}/5)
        </h3>
        {pins.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              계산 결과에서 핀 아이콘을 눌러 여기에 고정하세요.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
            {pins.map((pin) => {
              const r = results[pin.resultId];
              if (!r) return null;
              const Icon = typeIcons[r.type];
              const value = r.outputs[pin.displayKey];
              return (
                <Card key={pin.resultId} className="relative group">
                  <CardContent className="pt-4 pb-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2 text-muted-foreground mb-2">
                        <Icon className="h-4 w-4" />
                        <span className="text-xs">{typeLabels[r.type]}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => removePin(pin.resultId)}
                      >
                        <PinOff className="h-3 w-3" />
                      </Button>
                    </div>
                    <Link href={`${typeLinks[r.type]}?restore=${r.id}`}>
                      <p className="text-lg font-bold font-mono">
                        {typeof value === "number"
                          ? formatCurrency(value)
                          : value}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1 truncate">
                        {r.label}
                      </p>
                    </Link>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* 최근 계산 내역 */}
      <section>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">
          최근 계산 내역
        </h3>
        {history.length === 0 ? (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              아직 계산 내역이 없습니다. 계산기를 사용해보세요.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {history.slice(0, 20).map((item) => {
              const Icon = typeIcons[item.type];
              return (
                <div key={item.id} className="flex items-center gap-2">
                  <Link href={typeLinks[item.type]} className="flex-1">
                    <Card className="hover:bg-accent/50 transition-colors">
                      <CardContent className="py-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Icon className="h-4 w-4 text-muted-foreground" />
                            <div>
                              <p className="text-sm font-medium">{item.label}</p>
                              <p className="text-xs text-muted-foreground">
                                {new Date(item.timestamp).toLocaleString("ko-KR")}
                              </p>
                            </div>
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {typeLabels[item.type]}
                          </Badge>
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => removeFromHistory(item.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
