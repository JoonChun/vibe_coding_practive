import { WeeklyChart } from './WeeklyChart'
import { CategoryPie } from './CategoryPie'
import { HourlyHeatmap } from './HourlyHeatmap'

export function StatsView() {
  return (
    <div className="p-6 md:p-10 max-w-5xl mx-auto space-y-8">
      <header>
        <h2 className="text-3xl font-bold font-headline text-primary dark:text-[#00FF41]">Growth Stats</h2>
        <p className="text-on-surface-variant dark:text-slate-400 mt-1 text-sm">몰입의 여정을 돌아봐요, Bear.</p>
      </header>

      <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 md:p-8">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60 mb-4">Weekly Focus Distribution</h3>
        <WeeklyChart />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60 mb-4">Category Split</h3>
          <CategoryPie />
        </div>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60 mb-4">Hourly Heatmap</h3>
          <HourlyHeatmap />
        </div>
      </div>
    </div>
  )
}
