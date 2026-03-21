"use client";

import { useState, useMemo } from "react";
import { ArrowUpDown } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { UNIT_CATEGORIES, convertUnit } from "@/lib/calculators/unit";

export default function UnitPage() {
  const [categoryIndex, setCategoryIndex] = useState(0);
  const [fromUnit, setFromUnit] = useState(UNIT_CATEGORIES[0].units[0].id);
  const [toUnit, setToUnit] = useState(UNIT_CATEGORIES[0].units[1].id);
  const [inputValue, setInputValue] = useState(1);

  const category = UNIT_CATEGORIES[categoryIndex];

  const result = useMemo(
    () => convertUnit(inputValue, fromUnit, toUnit, category.name),
    [inputValue, fromUnit, toUnit, category.name]
  );

  const handleCategoryChange = (index: string) => {
    const i = parseInt(index);
    setCategoryIndex(i);
    setFromUnit(UNIT_CATEGORIES[i].units[0].id);
    setToUnit(UNIT_CATEGORIES[i].units[1].id);
    setInputValue(1);
  };

  const handleSwap = () => {
    const prevFrom = fromUnit;
    setFromUnit(toUnit);
    setToUnit(prevFrom);
    setInputValue(result);
  };

  const formatResult = (v: number) => {
    if (Math.abs(v) >= 1) return v.toLocaleString("ko-KR", { maximumFractionDigits: 6 });
    return v.toPrecision(6);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">단위 변환</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          다양한 단위를 간편하게 변환합니다.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6 space-y-5">
          <div className="space-y-2">
            <Label>카테고리</Label>
            <Select
              value={categoryIndex.toString()}
              onValueChange={handleCategoryChange}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {UNIT_CATEGORIES.map((cat, i) => (
                  <SelectItem key={cat.name} value={i.toString()}>
                    {cat.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-[1fr,auto,1fr] items-end gap-3">
            <div className="space-y-2">
              <Label>변환 전</Label>
              <Select value={fromUnit} onValueChange={setFromUnit}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {category.units.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                type="number"
                value={inputValue}
                onChange={(e) => setInputValue(Number(e.target.value))}
                className="font-mono text-lg"
              />
            </div>

            <Button
              variant="ghost"
              size="icon"
              onClick={handleSwap}
              className="mb-1"
            >
              <ArrowUpDown className="h-5 w-5" />
            </Button>

            <div className="space-y-2">
              <Label>변환 후</Label>
              <Select value={toUnit} onValueChange={setToUnit}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {category.units.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <div className="flex items-center h-10 px-3 rounded-md border border-border bg-muted">
                <span className="font-mono text-lg text-primary">
                  {formatResult(result)}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
