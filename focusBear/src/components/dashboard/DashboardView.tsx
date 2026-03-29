import { useState, useCallback } from 'react'
import { useApp } from '../../context/AppContext'
import { useTimer } from '../../hooks/useTimer'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { BearCharacter } from './BearCharacter'
import { Timer } from './Timer'
import { TimerControls } from './TimerControls'
import { MemoDialog } from './MemoDialog'
import { PawTrail } from './PawTrail'
import { addSession, getTodayTotal } from '../../db/sessions'

export function DashboardView() {
  const { state, dispatch } = useApp()
  const { start, pause, reset, getStartTimestamp } = useTimer()
  const { record } = useUndoRedo()
  const [memoOpen, setMemoOpen] = useState(false)
  const [pendingSession, setPendingSession] = useState<{
    start: number; end: number; duration: number; category: string
  } | null>(null)

  const handleReset = useCallback(() => {
    if (state.timerState === 'running' || state.timerState === 'paused') {
      const startTs = getStartTimestamp()
      if (startTs && state.elapsed >= 10) {
        const endTs = Date.now()
        setPendingSession({
          start: startTs,
          end: endTs,
          duration: state.elapsed,
          category: state.selectedCategory,
        })
        setMemoOpen(true)
      }
    }
    reset()
  }, [state.timerState, state.elapsed, state.selectedCategory, getStartTimestamp, reset])

  const saveSession = useCallback(async (memo: string) => {
    if (!pendingSession) return
    const session = { ...pendingSession, memo, isManual: false }
    await addSession(session)
    record({ type: 'ADD_SESSION', session })
    const total = await getTodayTotal()
    dispatch({ type: 'SET_TODAY_TOTAL', total })
    setMemoOpen(false)
    setPendingSession(null)
  }, [pendingSession, record, dispatch])

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] gap-8 py-12 px-6">
      {/* Greeting */}
      <div className="text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-on-surface-variant dark:text-slate-500">
          {new Date().getHours() < 12 ? 'Good Morning' : new Date().getHours() < 18 ? 'Good Afternoon' : 'Good Evening'}
        </p>
        <h2 className="font-headline text-2xl font-bold text-primary dark:text-[#00FF41] mt-0.5">
          집중할 준비가 됐나요?
        </h2>
      </div>

      {/* Bear character */}
      <BearCharacter
        mood={state.bearMood}
        elapsed={state.elapsed}
        timerMode={state.timerMode}
        timerState={state.timerState}
        animationEnabled={state.animationEnabled}
        pomodoroDuration={state.pomodoroDuration}
      />

      {/* Timer + Controls card */}
      <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-8 w-full max-w-sm flex flex-col items-center gap-6">
        <Timer
          elapsed={state.elapsed}
          mode={state.timerMode}
          timerState={state.timerState}
          pomodoroDuration={state.pomodoroDuration}
        />

        <TimerControls
          onStart={start}
          onPause={pause}
          onReset={handleReset}
        />
      </div>

      {/* Paw Trail — daily goal progress */}
      <PawTrail />

      <MemoDialog
        open={memoOpen}
        duration={pendingSession?.duration ?? 0}
        category={pendingSession?.category ?? ''}
        onSave={saveSession}
        onSkip={() => { setMemoOpen(false); setPendingSession(null) }}
      />
    </div>
  )
}
