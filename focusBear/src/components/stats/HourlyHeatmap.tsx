// src/components/stats/HourlyHeatmap.tsx
import { useEffect, useState } from 'react'
import { getSessionsByRange } from '../../db/sessions'

export function HourlyHeatmap() {
  const [hourData, setHourData] = useState<number[]>(Array(24).fill(0))

  useEffect(() => {
    const weekAgo = Date.now() - 7 * 24 * 60 * 60 * 1000
    getSessionsByRange(weekAgo, Date.now()).then(sessions => {
      const counts = Array(24).fill(0)
      for (const s of sessions) {
        const hour = new Date(s.start).getHours()
        counts[hour] += s.duration
      }
      setHourData(counts)
    })
  }, [])

  const max = Math.max(...hourData, 1)

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 shadow-sm">
      <h3 className="font-bold mb-4">시간대별 집중 패턴 (7일)</h3>
      <div className="flex items-end gap-1 h-20">
        {hourData.map((val, h) => (
          <div key={h} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full rounded-t"
              style={{
                height: `${(val / max) * 64}px`,
                minHeight: val > 0 ? 4 : 0,
                background: val > 0 ? 'var(--accent-color)' : '#E5E7EB',
                opacity: val > 0 ? 0.4 + 0.6 * (val / max) : 1,
              }}
              title={`${h}시 · ${Math.floor(val / 60)}분`}
            />
            {h % 6 === 0 && (
              <span className="text-[9px] text-gray-400">{h}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
