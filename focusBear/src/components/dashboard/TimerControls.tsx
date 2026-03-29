import { Play, Pause, Square, Clock, Timer as TimerIcon, ChevronDown } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { clsx } from 'clsx'
import { useState, useRef, useEffect } from 'react'
import type { TimerMode } from '../../types'

const PRESETS = [15, 25, 45, 60]

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

  const [durationOpen, setDurationOpen] = useState(false)
  const [customInput, setCustomInput] = useState('')
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!durationOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDurationOpen(false)
        setCustomInput('')
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [durationOpen])

  function setMode(mode: TimerMode) {
    if (!isRunning) {
      dispatch({ type: 'SET_TIMER_MODE', mode })
      setDurationOpen(false)
    }
  }

  function selectPreset(min: number) {
    dispatch({ type: 'SET_POMODORO_DURATION', minutes: min })
    setDurationOpen(false)
    setCustomInput('')
  }

  function submitCustom() {
    const n = parseInt(customInput, 10)
    if (Number.isFinite(n) && n >= 1 && n <= 120) {
      dispatch({ type: 'SET_POMODORO_DURATION', minutes: n })
      setDurationOpen(false)
      setCustomInput('')
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

      {state.timerMode === 'pomodoro' && (
        <div ref={dropdownRef} className="relative">
          <button
            onClick={() => { if (isIdle) setDurationOpen(o => !o) }}
            disabled={!isIdle}
            className={clsx(
              'flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium border transition-colors',
              isIdle
                ? 'border-[var(--accent-color)] text-[var(--accent-color)] hover:bg-[var(--accent-color)]/10 cursor-pointer'
                : 'border-gray-300 dark:border-gray-600 text-gray-400 cursor-default'
            )}
          >
            {state.pomodoroDuration}분
            {isIdle && <ChevronDown size={12} className={clsx('transition-transform', durationOpen && 'rotate-180')} />}
          </button>

          {durationOpen && (
            <div className="absolute top-full mt-2 left-1/2 -translate-x-1/2 z-10 bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 p-3 w-52">
              <p className="text-[10px] text-gray-400 uppercase tracking-widest mb-2 text-center">집중 시간</p>
              <div className="grid grid-cols-4 gap-1.5 mb-3">
                {PRESETS.map(min => (
                  <button
                    key={min}
                    onClick={() => selectPreset(min)}
                    className={clsx(
                      'py-1.5 rounded-lg text-xs font-medium transition-colors',
                      state.pomodoroDuration === min
                        ? 'bg-[var(--accent-color)] text-white'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                    )}
                  >
                    {min}분
                  </button>
                ))}
              </div>
              <div className="flex gap-1.5 items-center">
                <input
                  type="number"
                  min={1}
                  max={120}
                  placeholder="직접 입력"
                  value={customInput}
                  onChange={e => setCustomInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && submitCustom()}
                  className="flex-1 px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900 text-xs focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
                />
                <span className="text-xs text-gray-400">분</span>
                <button
                  onClick={submitCustom}
                  className="px-2 py-1 rounded-lg bg-[var(--accent-color)] text-white text-xs font-medium hover:opacity-90 transition-opacity"
                >
                  확인
                </button>
              </div>
            </div>
          )}
        </div>
      )}

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
          className={`w-16 h-16 rounded-full text-white flex items-center justify-center shadow-lg hover:opacity-90 active:scale-95 transition-all ${
            isPaused
              ? 'bg-amber-500 ring-4 ring-amber-300 dark:ring-amber-600 animate-pulse'
              : 'bg-[var(--accent-color)]'
          }`}
        >
          {isRunning ? <Pause size={24} /> : <Play size={24} className="ml-1" />}
        </button>

        <div className="w-12 h-12" />
      </div>

      <p className={`text-xs font-mono tracking-widest transition-opacity ${isPaused ? 'text-amber-500 animate-pulse opacity-100' : 'opacity-0 select-none'}`}>
        [ 일시정지 중 ]
      </p>
    </div>
  )
}
