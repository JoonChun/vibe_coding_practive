// src/components/stats/CategoryPie.tsx
import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import { getSessionsByRange } from '../../db/sessions'

interface PieData {
  name: string
  value: number
  color: string
}

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

export function CategoryPie() {
  const [data, setData] = useState<PieData[]>([])

  useEffect(() => {
    const monthAgo = Date.now() - 30 * 24 * 60 * 60 * 1000
    getSessionsByRange(monthAgo, Date.now()).then(sessions => {
      const map = new Map<string, number>()
      for (const s of sessions) {
        map.set(s.category, (map.get(s.category) ?? 0) + s.duration)
      }
      setData(Array.from(map.entries()).map(([name, val], i) => ({
        name,
        value: Math.floor(val / 60),
        color: COLORS[i % COLORS.length],
      })))
    })
  }, [])

  if (data.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 shadow-sm flex items-center justify-center h-48">
        <p className="text-sm text-gray-400">이번 달 기록이 없어요 🐻</p>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 shadow-sm">
      <h3 className="font-bold mb-4">카테고리 비중 (30일)</h3>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={75} dataKey="value" paddingAngle={3}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie>
          <Tooltip formatter={(v) => [`${v}분`, '']} />
          <Legend iconType="circle" iconSize={8} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
