import { useEffect, useState } from 'react'
import { WeeklyChart } from './WeeklyChart'
import { CategoryPie } from './CategoryPie'
import { HourlyHeatmap } from './HourlyHeatmap'
import { getMonthSummary, getCurrentStreak } from '../../db/sessions'

function formatHours(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0 && m > 0) return `${h}h ${m}m`
  if (h > 0) return `${h}h`
  return `${m}m`
}

export function StatsView() {
  const now = new Date()
  const [summary, setSummary] = useState({ totalSeconds: 0, sessionCount: 0 })
  const [streak, setStreak] = useState(0)

  useEffect(() => {
    getMonthSummary(now.getFullYear(), now.getMonth()).then(setSummary)
    getCurrentStreak().then(setStreak)
  }, [])

  return (
    <div className="p-6 md:p-10 max-w-5xl mx-auto space-y-8">
      <header>
        <h2 className="text-3xl font-bold font-headline text-primary dark:text-[#00FF41]">Growth Stats</h2>
        <p className="text-on-surface-variant dark:text-slate-400 mt-1 text-sm">몰입의 여정을 돌아봐요, Bear.</p>
      </header>

      {/* 3 Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Focus */}
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 relative overflow-hidden group">
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary/50 dark:text-[#00FF41]/50">Total Focus (이번 달)</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-headline text-primary dark:text-[#00FF41]">
              {formatHours(summary.totalSeconds)}
            </span>
          </div>
          <div className="absolute text-8xl opacity-5 -right-3 -bottom-3 text-primary dark:text-[#00FF41] select-none">🐾</div>
        </div>

        {/* Sessions */}
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 relative overflow-hidden">
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary/50 dark:text-[#00FF41]/50">Deep Work Sessions</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-headline text-primary dark:text-[#00FF41]">
              {summary.sessionCount}
            </span>
            <span className="font-mono text-xs text-on-surface-variant">세션 이번 달</span>
          </div>
          <div className="absolute text-8xl opacity-5 -right-3 -bottom-3 text-primary dark:text-[#00FF41] select-none">⏱</div>
        </div>

        {/* Streak - honey gradient */}
        <div className="honey-gradient rounded-4xl shadow-fur-lg p-6 text-white relative overflow-hidden">
          <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-white/60">Flow Streak</span>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-headline">{streak}일</span>
            {streak > 0 && <span className="font-mono text-xs text-white/80">연속 집중!</span>}
          </div>
          <div className="mt-3 flex gap-1">
            {Array.from({ length: 7 }).map((_, i) => (
              <div key={i} className={`h-1.5 flex-1 rounded-full ${i < Math.min(streak, 7) ? 'bg-white' : 'bg-white/20'}`} />
            ))}
          </div>
          <div className="absolute text-8xl opacity-10 -right-3 -bottom-3 text-white select-none">🏆</div>
        </div>
      </div>

      {/* Weekly chart + Category split */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 md:p-8">
          <h3 className="font-bold text-lg text-primary dark:text-[#00FF41] mb-1">Weekly Focus Distribution</h3>
          <p className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary/50 dark:text-[#00FF41]/50 mb-6">최근 7일 집중 시간</p>
          <WeeklyChart />
        </div>

        <div className="lg:col-span-4 bg-surface-container-high dark:bg-white/5 rounded-4xl fur-shadow p-6 md:p-8">
          <h3 className="font-bold text-lg text-primary dark:text-[#00FF41] mb-6">Category Split</h3>
          <CategoryPie />
        </div>
      </div>

      {/* Weekday efficiency heatmap */}
      <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 md:p-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-6">
          <div>
            <h3 className="font-bold text-lg text-primary dark:text-[#00FF41]">Efficiency Heatmap</h3>
            <p className="text-sm text-on-surface-variant dark:text-slate-400 font-medium">가장 날카로운 요일은 언제예요, Bear?</p>
          </div>
          <div className="flex items-center gap-3 bg-surface-container-high dark:bg-white/5 rounded-full px-4 py-2">
            <span className="font-mono text-[9px] text-on-surface-variant uppercase">DULL</span>
            <div className="flex gap-1">
              {[0.1, 0.3, 0.6, 0.9].map(o => (
                <div key={o} className="w-4 h-4 rounded-sm" style={{ background: `rgba(108, 47, 0, ${o})` }} />
              ))}
            </div>
            <span className="font-mono text-[9px] text-on-surface-variant uppercase">SHARP</span>
          </div>
        </div>
        <HourlyHeatmap />
      </div>
    </div>
  )
}
