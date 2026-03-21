"use client";

import { Pin, PinOff } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useCountUp } from "@/hooks/use-count-up";
import { cn } from "@/lib/utils";

interface ResultCardProps {
  label: string;
  value: number;
  format?: (value: number) => string;
  isPinned?: boolean;
  onTogglePin?: () => void;
  className?: string;
}

export function ResultCard({
  label,
  value,
  format,
  isPinned,
  onTogglePin,
  className,
}: ResultCardProps) {
  const animated = useCountUp(value);
  const displayValue = format
    ? format(Math.round(animated))
    : Math.round(animated).toLocaleString("ko-KR");

  return (
    <Card className={cn("relative", className)}>
      <CardContent className="pt-4 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold font-mono mt-1">{displayValue}</p>
          </div>
          {onTogglePin && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={onTogglePin}
            >
              {isPinned ? (
                <PinOff className="h-4 w-4 text-primary" />
              ) : (
                <Pin className="h-4 w-4 text-muted-foreground" />
              )}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
