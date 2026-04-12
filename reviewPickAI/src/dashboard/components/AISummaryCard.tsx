import { Sparkles, TrendingUp, TrendingDown } from 'lucide-react';
import type { AnalysisResult } from '@/types';

interface AISummaryCardProps {
  summary: AnalysisResult['summary'];
}

export function AISummaryCard({ summary }: AISummaryCardProps) {
  return (
    <div className="bg-surface rounded-3xl p-8 shadow-whisper relative overflow-hidden h-full">
      {/* 배경 워터마크 */}
      <div className="absolute top-0 right-0 p-8 opacity-[0.04] pointer-events-none">
        <Sparkles size={140} />
      </div>

      {/* 헤더 */}
      <div className="flex items-center gap-2 text-primary mb-6 relative">
        <Sparkles size={18} fill="currentColor" />
        <h2 className="font-headline font-semibold text-[16px]">AI 인사이트 요약</h2>
      </div>

      {/* 종합 평가 (히어로 텍스트) */}
      <div className="space-y-3 relative max-w-2xl">
        <p className="text-[19px] font-medium leading-relaxed text-on-surface">
          {summary.overall}
        </p>

        {/* 배지 */}
        <div className="flex gap-2.5 pt-2">
          <span className="px-3 py-1 bg-primary/10 text-primary text-[10px] font-bold rounded-full uppercase tracking-wider">
            AI 종합 평가
          </span>
          <span className="px-3 py-1 bg-surface-container text-secondary text-[10px] font-bold rounded-full uppercase tracking-wider">
            리뷰 기반
          </span>
        </div>
      </div>

      {/* 긍정 / 부정 요약 행 */}
      <div className="mt-6 space-y-3 relative">
        <SummaryRow
          icon={<TrendingUp size={14} className="text-primary" />}
          label="긍정 핵심"
          text={summary.positive}
          labelColor="text-primary"
          bg="bg-primary/5"
        />
        <SummaryRow
          icon={<TrendingDown size={14} className="text-negative" />}
          label="부정 핵심"
          text={summary.negative}
          labelColor="text-negative"
          bg="bg-negative/5"
        />
      </div>
    </div>
  );
}

function SummaryRow({
  icon,
  label,
  text,
  labelColor,
  bg,
}: {
  icon: React.ReactNode;
  label: string;
  text: string;
  labelColor: string;
  bg: string;
}) {
  return (
    <div className={`flex gap-3 p-3.5 rounded-2xl ${bg}`}>
      <div className="flex-shrink-0 mt-0.5">{icon}</div>
      <div>
        <p className={`text-[10px] font-bold ${labelColor} mb-0.5 uppercase tracking-wide`}>
          {label}
        </p>
        <p className="text-[13px] text-on-surface leading-relaxed">{text}</p>
      </div>
    </div>
  );
}
