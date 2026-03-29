"use client";

import { useState, useEffect } from "react";
import { format, parse } from "date-fns";
import { ko } from "date-fns/locale";
import { Plus, Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  calculateDday,
  formatDdayDisplay,
  formatBreakdown,
  type DdayEvent,
} from "@/lib/calculators/dday";
import { generateId } from "@/lib/utils";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "dday-events";

function loadEvents(): DdayEvent[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveEvents(events: DdayEvent[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(events));
}

export default function DdayPage() {
  const [events, setEvents] = useState<DdayEvent[]>([]);
  const [newName, setNewName] = useState("");
  const [newDate, setNewDate] = useState("");
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setEvents(loadEvents());
    setMounted(true);
  }, []);

  const selectedDate = newDate
    ? parse(newDate, "yyyy-MM-dd", new Date())
    : undefined;

  const handleCalendarSelect = (date: Date | undefined) => {
    if (date) {
      setNewDate(format(date, "yyyy-MM-dd"));
      setCalendarOpen(false);
    }
  };

  const handleAdd = () => {
    if (!newName || !newDate) return;
    const event: DdayEvent = {
      id: generateId(),
      name: newName,
      targetDate: newDate,
    };
    const updated = [...events, event];
    setEvents(updated);
    saveEvents(updated);
    setNewName("");
    setNewDate("");
  };

  const handleRemove = (id: string) => {
    const updated = events.filter((e) => e.id !== id);
    setEvents(updated);
    saveEvents(updated);
  };

  const sortedEvents = [...events].sort((a, b) => {
    const da = Math.abs(calculateDday(a.targetDate).daysRemaining);
    const db = Math.abs(calculateDday(b.targetDate).daysRemaining);
    return da - db;
  });

  if (!mounted) return null;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">디데이 계산기</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          중요한 날까지 남은 일수를 관리합니다.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">새 디데이 추가</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 space-y-1">
              <Label>이름</Label>
              <Input
                placeholder="예: 여행 출발일"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
            </div>
            <div className="flex-1 space-y-1">
              <Label>날짜</Label>
              <div className="flex gap-2">
                <Input
                  type="date"
                  value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                  className="flex-1"
                />
              </div>
            </div>
            <div className="flex items-end">
              <Button onClick={handleAdd} disabled={!newName || !newDate}>
                <Plus className="h-4 w-4 mr-1" />
                추가
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {sortedEvents.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              등록된 디데이가 없습니다. 위에서 추가해보세요.
            </CardContent>
          </Card>
        ) : (
          sortedEvents.map((event) => {
            const result = calculateDday(event.targetDate);
            const { breakdown } = result;
            return (
              <Card key={event.id}>
                <CardContent className="py-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium truncate">{event.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {result.targetDateFormatted}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {result.daysRemaining === 0
                          ? "오늘입니다!"
                          : result.isPast
                            ? `${formatBreakdown(breakdown)} 지남`
                            : `${formatBreakdown(breakdown)} 남음`}
                      </p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <Badge
                          variant={result.isPast ? "secondary" : "default"}
                          className="text-lg font-mono px-3 py-1"
                        >
                          {formatDdayDisplay(result.daysRemaining)}
                        </Badge>
                        <p className="text-xs text-muted-foreground mt-1 text-center">
                          {Math.abs(result.daysRemaining)}일
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRemove(event.id)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}
