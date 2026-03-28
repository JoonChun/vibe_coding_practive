import { Play, Pause, Square, Clock, Timer as TimerIcon } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { clsx } from 'clsx'
import type { TimerMode } from '../../types'

interface Props {
  onStart: () => void
  onPause: () => void
  onReset: () => void
}

export function TimerControls({ onStart, onPause, onReset }: Props) {
  const { state, dispatch } = useApp()
  const { categories } = state

  const isRunning = state.timerState === 'running'
  const isPaused = state.timerState === 'paused'
  const isIdle = state.timerState === 'idle'

  void isPaused

  function setMode(mode: TimerMode) {
    if (!isRunning) {
      dispatch({ type: 'SET_TIMER_MODE', mode })
    }
  }

  return (
    <div className="flex flex-col items-center gap-4 w-full max-w-sm">
      <div className="flex rounded-xl bg-gray-100 dark:bg-gray-800 p-1 gap-1">
        {(['stopwatch', 'pomodoro'] as TimerMode[]).map(mode => (
          <button
            key={mode}
            onClick={() => setMode(mode)}
            disabled={isRunning}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors',
              state.timerMode === mode
                ? 'bg-white dark:bg-gray-700 text-[var(--accent-color)] shadow-sm'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 disabled:opacity-50'
            )}
          >
            {mode === 'stopwatch' ? <Clock size={14} /> : <TimerIcon size={14} />}
            {mode === 'stopwatch' ? '스톱워치' : '타이머'}
          </button>
        ))}
      </div>

      <select
        value={state.selectedCategory}
        onChange={e => dispatch({ type: 'SET_CATEGORY', category: e.target.value })}
        disabled={isRunning}
        className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)] disabled:opacity-50"
      >
        {categories.map(c => (
          <option key={c.id} value={c.name}>{c.name}</option>
        ))}
      </select>

      <div className="flex items-center gap-3">
        <button
          onClick={onReset}
          disabled={isIdle}
          className="w-12 h-12 rounded-full border-2 border-gray-300 dark:border-gray-600 flex items-center justify-center text-gray-400 hover:border-red-400 hover:text-red-400 disabled:opacity-30 transition-colors"
        >
          <Square size={18} />
        </button>

        <button
          onClick={isRunning ? onPause : onStart}
          className="w-16 h-16 rounded-full bg-[var(--accent-color)] text-white flex items-center justify-center shadow-lg hover:opacity-90 active:scale-95 transition-all"
        >
          {isRunning ? <Pause size={24} /> : <Play size={24} className="ml-1" />}
        </button>

        <div className="w-12 h-12" />
      </div>
    </div>
  )
}
