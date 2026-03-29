import { useEffect, useState } from 'react'
import { getWeekdayStats } from '../../db/sessions'

interface WeekdayData { weekday: string; score: number; label: string }

export function HourlyHeatmap() {
  const [data, setData] = useState<WeekdayData[]>([])

  useEffect(() => { getWeekdayStats().then(setData) }, [])

  if (data.length === 0) return null

  const maxScore = Math.max(...data.map(d => d.score), 1)

  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5">
        {data.map((d) => {
          const intensity = d.score / maxScore
          return (
            <div key={d.weekday}
              className="flex flex-col items-center text-center p-2 rounded-2xl bg-surface-container-highest/40 dark:bg-white/5">
              <span className="font-mono text-[9px] text-on-surface-variant dark:text-slate-500 mb-2 uppercase">{d.weekday}</span>
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-white mb-1.5"
                style={{
                  background: d.score === 0
                    ? 'rgba(108, 47, 0, 0.1)'
                    : `rgba(108, 47, 0, ${0.2 + intensity * 0.8})`,
                  color: intensity > 0.5 ? 'white' : '#6c2f00',
                }}
              >
                <span className="font-mono text-[10px] font-bold">{d.score}</span>
              </div>
              <span className="font-mono text-[8px] font-bold text-primary dark:text-[#00FF41] uppercase leading-tight"
                style={{ opacity: d.score === 0 ? 0.3 : 0.8 }}>
                {d.label}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
