// src/components/calendar/HeatmapCell.tsx
import { clsx } from 'clsx'
import { useApp } from '../../context/AppContext'

function getIntensityLevel(seconds: number): number {
  if (seconds === 0) return 0
  if (seconds < 30 * 60) return 1
  if (seconds < 60 * 60) return 2
  if (seconds < 2 * 60 * 60) return 3
  return 4
}

// Returns inline style for the cell background based on intensity and theme
function getCellStyle(level: number, isDark: boolean): React.CSSProperties {
  if (level === 0) return {}
  const intensities = [0, 0.15, 0.35, 0.65, 1.0]
  const intensity = intensities[level]

  if (isDark) {
    // Dark theme: #00FF41 green with varying alpha
    const alpha = Math.round(intensity * 255).toString(16).padStart(2, '0')
    return { backgroundColor: `#00FF41${alpha}` }
  } else {
    // Light theme: honey brown #6c2f00
    return { backgroundColor: `rgba(108, 47, 0, ${intensity})` }
  }
}

interface Props {
  date: Date
  totalSeconds: number
  isToday: boolean
  isCurrentMonth: boolean
  isSelected: boolean
  onClick: () => void
}

export function HeatmapCell({ date, totalSeconds, isToday, isCurrentMonth, isSelected, onClick }: Props) {
  const { state } = useApp()
  const isDark = state.theme === 'dark'
  const level = getIntensityLevel(totalSeconds)
  const hasSessions = totalSeconds > 0
  const minutes = Math.floor(totalSeconds / 60)

  const cellStyle = isCurrentMonth ? getCellStyle(level, isDark) : {}
  const useWhiteText = level >= 3 && isCurrentMonth

  return (
    <button
      onClick={onClick}
      title={`${date.getDate()}일 · ${minutes}분 집중`}
      style={cellStyle}
      className={clsx(
        'relative aspect-square w-full rounded-xl p-2 transition-all cursor-pointer',
        // Base bg when no data
        isCurrentMonth
          ? level === 0 ? 'bg-surface-container-highest dark:bg-gray-800' : ''
          : 'bg-transparent opacity-30',
        // Hover effect
        isCurrentMonth && 'hover:opacity-75',
        // Selected ring
        isSelected && 'ring-4 ring-primary-fixed ring-offset-2 ring-offset-background scale-105 z-10 shadow-lg',
        // Today indicator
        isToday && !isSelected && 'ring-2 ring-primary/40 dark:ring-green-400/40 ring-offset-1',
      )}
    >
      <span className={clsx(
        'font-mono text-sm font-bold leading-none block',
        useWhiteText
          ? 'text-white'
          : isDark
            ? 'text-gray-100'
            : 'text-on-surface',
        !isCurrentMonth && 'opacity-40',
      )}>
        {date.getDate()}
      </span>
      {hasSessions && isCurrentMonth && (
        <span
          className={clsx(
            'absolute bottom-1 right-1 text-[10px] select-none',
            useWhiteText ? 'opacity-90' : 'opacity-70',
          )}
          aria-hidden="true"
        >
          🐾
        </span>
      )}
    </button>
  )
}
