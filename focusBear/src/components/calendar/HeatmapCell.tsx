// src/components/calendar/HeatmapCell.tsx
import { clsx } from 'clsx'

function getIntensityLevel(seconds: number): number {
  if (seconds === 0) return 0
  if (seconds < 30 * 60) return 1
  if (seconds < 60 * 60) return 2
  if (seconds < 2 * 60 * 60) return 3
  return 4
}

const LIGHT_COLORS = ['bg-gray-100', 'bg-amber-100', 'bg-amber-200', 'bg-amber-400', 'bg-amber-600']
const DARK_COLORS = ['bg-gray-800', 'bg-green-900', 'bg-green-700', 'bg-green-500', 'bg-green-300']

interface Props {
  date: Date
  totalSeconds: number
  isToday: boolean
  isCurrentMonth: boolean
  onClick: () => void
}

export function HeatmapCell({ date, totalSeconds, isToday, isCurrentMonth, onClick }: Props) {
  const level = getIntensityLevel(totalSeconds)
  const hasSessions = totalSeconds > 0

  return (
    <button
      onClick={onClick}
      title={`${date.getDate()}일 · ${Math.floor(totalSeconds / 60)}분 집중`}
      className={clsx(
        'relative aspect-square w-full rounded-lg transition-all hover:ring-2 hover:ring-[var(--accent-color)] hover:ring-offset-1',
        isCurrentMonth ? LIGHT_COLORS[level] : 'bg-gray-50 dark:bg-gray-900 opacity-40',
        isToday && 'ring-2 ring-[var(--accent-color)] ring-offset-1',
      )}
    >
      <span className={clsx(
        'absolute top-1 left-1.5 text-xs',
        level >= 3 ? 'text-white' : 'text-gray-600 dark:text-gray-300',
        !isCurrentMonth && 'opacity-50'
      )}>
        {date.getDate()}
      </span>
      {hasSessions && (
        <span className="absolute bottom-0.5 right-0.5 text-[10px]">🐾</span>
      )}
    </button>
  )
}
