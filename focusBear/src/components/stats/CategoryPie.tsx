import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts'
import { getSessionsByRange } from '../../db/sessions'

interface PieData { name: string; value: number; color: string }

// Category colors matching the warm design system
const CAT_COLORS = ['#6c2f00', '#8b4513', '#006e16', '#394156', '#a05c2c', '#2d5a3d']

export function CategoryPie() {
  const [data, setData] = useState<PieData[]>([])

  useEffect(() => {
    const monthAgo = Date.now() - 30 * 24 * 60 * 60 * 1000
    getSessionsByRange(monthAgo, Date.now()).then(sessions => {
      const map = new Map<string, number>()
      for (const s of sessions) map.set(s.category, (map.get(s.category) ?? 0) + s.duration)
      setData(Array.from(map.entries())
        .sort((a, b) => b[1] - a[1])
        .map(([name, val], i) => ({ name, value: Math.floor(val / 60), color: CAT_COLORS[i % CAT_COLORS.length] })))
    })
  }, [])

  const total = data.reduce((s, d) => s + d.value, 0)

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-48">
        <p className="font-mono text-xs text-on-surface-variant">이번 달 기록이 없어요 🐻</p>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-center mb-4">
        <div className="relative w-36 h-36">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={data} cx="50%" cy="50%" innerRadius={44} outerRadius={64} dataKey="value" paddingAngle={2} startAngle={90} endAngle={-270}>
                {data.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip formatter={(v) => [`${v}분`, '']} contentStyle={{ borderRadius: 12, border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono text-lg font-bold text-primary dark:text-[#00FF41]">{Math.floor(total / 60)}h</span>
            <span className="font-mono text-[8px] text-on-surface-variant uppercase tracking-wide">이번 달</span>
          </div>
        </div>
      </div>
      <div className="space-y-2.5 mt-2">
        {data.slice(0, 4).map((d) => (
          <div key={d.name} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-5 rounded-full" style={{ background: d.color }} />
              <span className="font-semibold text-xs text-on-surface dark:text-slate-200">{d.name}</span>
            </div>
            <span className="font-mono text-xs text-on-surface-variant dark:text-slate-400">
              {total > 0 ? Math.round(d.value / total * 100) : 0}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
