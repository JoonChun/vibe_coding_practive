// src/components/stats/WeeklyChart.tsx
import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { getSessionsByRange } from '../../db/sessions'

interface DayData {
  day: string
  minutes: number
  isToday: boolean
}

export function WeeklyChart() {
  const [data, setData] = useState<DayData[]>([])

  useEffect(() => {
    const today = new Date()
    const promises = Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today)
      d.setDate(today.getDate() - (6 - i))
      d.setHours(0, 0, 0, 0)
      const next = new Date(d)
      next.setDate(d.getDate() + 1)
      return getSessionsByRange(d.getTime(), next.getTime()).then(sessions => ({
        day: d.toLocaleDateString('ko-KR', { weekday: 'short' }),
        minutes: Math.floor(sessions.reduce((s, r) => s + r.duration, 0) / 60),
        isToday: i === 6,
      }))
    })
    Promise.all(promises).then(setData)
  }, [])

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 shadow-sm">
      <h3 className="font-bold mb-4">주간 집중 시간</h3>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} barSize={28}>
          <XAxis dataKey="day" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis hide />
          <Tooltip
            formatter={(v) => [`${v}분`, '집중']}
            contentStyle={{ borderRadius: 8, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
          />
          <Bar dataKey="minutes" radius={[6, 6, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.isToday ? 'var(--accent-color)' : '#E5E7EB'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
