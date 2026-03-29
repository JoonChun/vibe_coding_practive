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
        className="font-mono text-6xl font-bold tabular-nums tracking-widest text-[var(--accent-color)]"
        style={{ fontFamily: '"JetBrains Mono", monospace' }}
      >
        {formatTime(display)}
      </span>
      {mode === 'pomodoro' && (
        <p className="text-xs text-gray-400 mt-1 font-mono">
          POMODORO {timerState === 'running' ? '▶' : '⏸'}
        </p>
      )}
    </div>
  )
}
