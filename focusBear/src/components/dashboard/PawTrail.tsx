import { useApp } from '../../context/AppContext'

const MILESTONES = [0.25, 0.5, 0.75, 1.0]

export function PawTrail() {
  const { state } = useApp()
  const todayMinutes = Math.floor(state.todayTotal / 60)
  const goalMinutes = state.dailyGoal
  const progress = Math.min(todayMinutes / goalMinutes, 1)
  const goalReached = todayMinutes >= goalMinutes

  // Find next milestone
  const nextMilestone = MILESTONES.find(m => m > progress)
  const nextMilestoneMinutes = nextMilestone ? Math.ceil(nextMilestone * goalMinutes) : null
  const minutesLeft = nextMilestoneMinutes ? nextMilestoneMinutes - todayMinutes : 0

  return (
    <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 w-full max-w-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono text-[9px] uppercase tracking-[0.2em] text-primary/50 dark:text-[#00FF41]/50">
          Today's Paw Trail
        </span>
        <span className="font-mono text-xs font-bold text-primary dark:text-[#00FF41]">
          {todayMinutes}분 / {goalMinutes}분
        </span>
      </div>

      {/* Progress bar + milestone paws */}
      <div className="relative mt-4 mb-2">
        {/* Track */}
        <div className="h-2 bg-surface-container-highest dark:bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full honey-gradient dark:bg-[#00FF41] rounded-full transition-all duration-700"
            style={{ width: `${progress * 100}%` }}
          />
        </div>

        {/* Milestone paw markers */}
        {MILESTONES.map(m => {
          const reached = progress >= m
          const isGoal = m === 1.0
          return (
            <div
              key={m}
              className="absolute top-1/2 -translate-y-1/2 flex flex-col items-center"
              style={{ left: `calc(${m * 100}% - ${isGoal ? '8px' : '8px'})` }}
            >
              <span
                className={`text-base leading-none transition-all duration-500 ${
                  reached ? 'opacity-100 scale-110' : 'opacity-30 scale-90'
                }`}
              >
                {isGoal ? '🏆' : '🐾'}
              </span>
            </div>
          )
        })}
      </div>

      {/* Status text */}
      <div className="mt-4 text-center">
        {goalReached ? (
          <p className="font-headline font-bold text-sm text-primary dark:text-[#00FF41]">
            🎉 목표 달성! 오늘 정말 잘했어요, Bear.
          </p>
        ) : nextMilestoneMinutes ? (
          <p className="font-mono text-[10px] text-on-surface-variant dark:text-slate-400">
            Next milestone in{' '}
            <span className="font-bold text-primary dark:text-[#00FF41]">{minutesLeft}분</span>
          </p>
        ) : null}
      </div>
    </div>
  )
}
