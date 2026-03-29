import type { TimerMode } from '../../types'

function pad(n: number): string {
  return n.toString().padStart(2, '0')
}

function formatTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${pad(h)}:${pad(m)}:${pad(s)}`
  return `${pad(m)}:${pad(s)}`
}

interface Props {
  elapsed: number
  mode: TimerMode
  timerState: string
  pomodoroDuration: number
}

export function Timer({ elapsed, mode, timerState, pomodoroDuration }: Props) {
  const display = mode === 'pomodoro'
    ? Math.max(0, pomodoroDuration * 60 - elapsed)
    : elapsed

  return (
    <div className="text-center">
      <span
        className="font-mono text-6xl font-bold tabular-nums tracking-widest text-primary dark:text-[#00FF41]"
        style={{ fontFamily: '"JetBrains Mono", monospace' }}
      >
        {formatTime(display)}
      </span>
      {mode === 'pomodoro' && (
        <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-on-surface-variant dark:text-slate-500 mt-1">
          Pomodoro {timerState === 'running' ? '▶' : timerState === 'paused' ? '⏸' : '■'}
        </p>
      )}
    </div>
  )
}
