import { useEffect, useRef } from 'react';
import { Chart, ArcElement, DoughnutController, Tooltip, Legend } from 'chart.js';
import type { AnalysisResult } from '@/types';
import { COLORS } from '@/constants';

Chart.register(ArcElement, DoughnutController, Tooltip, Legend);

interface SentimentChartProps {
  sentiment: AnalysisResult['sentiment'];
}

export function SentimentChart({ sentiment }: SentimentChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<Chart | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;

    chartRef.current?.destroy();

    const { positiveCount, negativeCount, neutralCount } = sentiment;
    const total = positiveCount + negativeCount + neutralCount;

    chartRef.current = new Chart(canvasRef.current, {
      type: 'doughnut',
      data: {
        labels: ['긍정', '부정', '중립'],
        datasets: [
          {
            data: [positiveCount, negativeCount, neutralCount],
            backgroundColor: [COLORS.PRIMARY, COLORS.NEGATIVE, '#E0E3E5'],
            borderWidth: 0,
            hoverOffset: 6,
          },
        ],
      },
      options: {
        cutout: '74%',
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const val = ctx.parsed;
                const pct = total > 0 ? Math.round((val / total) * 100) : 0;
                return ` ${ctx.label}: ${val}개 (${pct}%)`;
              },
            },
          },
        },
        animation: { animateRotate: true, duration: 600 },
      },
    });

    return () => {
      chartRef.current?.destroy();
    };
  }, [sentiment]);

  const { positivePercent, negativePercent } = sentiment;
  const neutralPercent = 100 - positivePercent - negativePercent;

  return (
    <div className="bg-surface rounded-3xl p-8 shadow-whisper flex flex-col h-full">
      <h2 className="font-headline font-semibold text-[16px] text-on-surface mb-8">소비자 감성</h2>

      {/* 도넛 차트 + 중앙 수치 */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="relative w-48 h-48 mb-8">
          <canvas ref={canvasRef} />
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <span className="text-[34px] font-bold font-headline text-primary leading-none">
              {positivePercent}%
            </span>
            <span className="text-[10px] text-secondary font-bold uppercase tracking-widest mt-1">
              긍정
            </span>
          </div>
        </div>

        {/* 범례 */}
        <div className="flex gap-6 w-full justify-center">
          <LegendItem
            color={COLORS.PRIMARY}
            label="긍정"
            percent={positivePercent}
            count={sentiment.positiveCount}
          />
          <LegendItem
            color={COLORS.NEGATIVE}
            label="부정"
            percent={negativePercent}
            count={sentiment.negativeCount}
          />
          <LegendItem
            color="#E0E3E5"
            label="중립"
            percent={neutralPercent}
            count={sentiment.neutralCount}
          />
        </div>
      </div>
    </div>
  );
}

function LegendItem({
  color,
  label,
  percent,
  count,
}: {
  color: string;
  label: string;
  percent: number;
  count: number;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-[10px] font-bold text-secondary uppercase tracking-wider">{label}</span>
      <span className="text-[16px] font-bold text-on-surface">{percent}%</span>
      <span className="text-[11px] text-on-surface-variant">{count.toLocaleString()}개</span>
    </div>
  );
}
