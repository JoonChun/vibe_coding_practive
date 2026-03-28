import { useState, useCallback } from 'react'
import { useApp } from '../../context/AppContext'
import { useTimer } from '../../hooks/useTimer'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { BearCharacter } from './BearCharacter'
import { Timer } from './Timer'
import { TimerControls } from './TimerControls'
import { MemoDialog } from './MemoDialog'
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
    const session = {
      ...pendingSession,
      memo,
      isManual: false,
    }
    await addSession(session)
    record({ type: 'ADD_SESSION', session })
    const total = await getTodayTotal()
    dispatch({ type: 'SET_TODAY_TOTAL', total })
    setMemoOpen(false)
    setPendingSession(null)
  }, [pendingSession, record, dispatch])

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-3.5rem)] gap-8 py-8 px-4">
      <BearCharacter
        mood={state.bearMood}
        elapsed={state.elapsed}
        timerMode={state.timerMode}
        animationEnabled={state.animationEnabled}
      />

      <Timer
        elapsed={state.elapsed}
        mode={state.timerMode}
        timerState={state.timerState}
      />

      <TimerControls
        onStart={start}
        onPause={pause}
        onReset={handleReset}
      />

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
