import { useEffect, useState } from 'react'
import { getWeeklyData } from '../../db/sessions'

interface DayData { day: string; minutes: number; isToday: boolean }

export function WeeklyChart() {
  const [data, setData] = useState<DayData[]>([])

  useEffect(() => { getWeeklyData().then(setData) }, [])

  const maxMin = Math.max(...data.map(d => d.minutes), 1)

  return (
    <div>
      <div className="h-48 flex items-end justify-between gap-3 pb-4 border-b border-outline-variant/15 dark:border-white/5">
        {data.map((d, i) => {
          const heightPct = Math.max((d.minutes / maxMin) * 100, d.minutes > 0 ? 8 : 0)
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-2 group">
              {d.minutes > 0 && (
                <span className="font-mono text-[9px] text-on-surface-variant dark:text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity">
                  {d.minutes}분
                </span>
              )}
              <div className="w-full flex justify-center">
                <div
                  className={`w-5 rounded-t-lg transition-all duration-300 group-hover:opacity-80 ${
                    d.isToday ? 'honey-gradient' : 'bg-primary/15 dark:bg-[#00FF41]/15'
                  }`}
                  style={{ height: `${Math.max(heightPct * 1.5, d.minutes > 0 ? 6 : 2)}px` }}
                />
              </div>
              <span className="font-mono text-[10px] text-on-surface-variant dark:text-slate-500 uppercase">{d.day}</span>
            </div>
          )
        })}
      </div>
      <div className="flex justify-center gap-6 mt-4">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full honey-gradient" />
          <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest">오늘</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-primary/15 dark:bg-[#00FF41]/15" />
          <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-widest">이전</span>
        </div>
      </div>
    </div>
  )
}
