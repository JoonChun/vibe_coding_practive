import { ReactNode } from "react";

interface CalculatorLayoutProps {
  title: string;
  description?: string;
  inputSlot: ReactNode;
  resultSlot: ReactNode;
}

export function CalculatorLayout({
  title,
  description,
  inputSlot,
  resultSlot,
}: CalculatorLayoutProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">{title}</h2>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">{inputSlot}</div>
        <div className="space-y-4">{resultSlot}</div>
      </div>
    </div>
  );
}
