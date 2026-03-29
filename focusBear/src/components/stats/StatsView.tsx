// src/components/stats/StatsView.tsx
import { WeeklyChart } from './WeeklyChart'
import { CategoryPie } from './CategoryPie'
import { HourlyHeatmap } from './HourlyHeatmap'

export function StatsView() {
  return (
    <div className="p-6 max-w-2xl mx-auto space-y-4">
      <h2 className="text-xl font-bold">성장 통계 📊</h2>
      <WeeklyChart />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <CategoryPie />
        <HourlyHeatmap />
      </div>
    </div>
  )
}
