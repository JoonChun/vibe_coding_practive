"use client";

import { ReactNode } from "react";
import { ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ChartContainerProps {
  title?: string;
  height?: number;
  children: ReactNode;
}

export function ChartContainer({
  title,
  height = 300,
  children,
}: ChartContainerProps) {
  return (
    <Card>
      {title && (
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium">{title}</CardTitle>
        </CardHeader>
      )}
      <CardContent className="pb-4">
        <ResponsiveContainer width="100%" height={height}>
          {children as React.ReactElement}
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}

export const CHART_COLORS = {
  primary: "#34d399",
  secondary: "#6ee7b7",
  tertiary: "#059669",
  quaternary: "#047857",
  muted: "#065f46",
} as const;
