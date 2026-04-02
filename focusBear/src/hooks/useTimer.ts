import { useRef, useCallback, useEffect } from 'react'
import { useApp } from '../context/AppContext'
import type { WorkerMessage } from '../types'

export function useTimer() {
  const { state, dispatch } = useApp()
  const workerRef = useRef<Worker | null>(null)
  const startTimestampRef = useRef<number | null>(null)

  useEffect(() => {
    workerRef.current = new Worker(
      new URL('../workers/timer.worker.ts', import.meta.url),
      { type: 'module' }
    )
    workerRef.current.onmessage = (e: MessageEvent<WorkerMessage>) => {
      const msg = e.data
      if (msg.type === 'DONE') {
        dispatch({ type: 'SET_TIMER_STATE', timerState: 'idle' })
        dispatch({ type: 'SET_ELAPSED', elapsed: 0 })
        if (Notification.permission === 'granted') {
          new Notification('🐻 FocusBear', { body: '포모도로 완료! 잠깐 쉬어가세요 🍯' })
        }
        if ('vibrate' in navigator) {
          navigator.vibrate([200, 100, 200])
        }
      } else {
        dispatch({ type: 'SET_ELAPSED', elapsed: msg.elapsed })
      }
    }
    return () => {
      workerRef.current?.terminate()
    }
  }, [dispatch])

  const start = useCallback(() => {
    startTimestampRef.current = Date.now()
    workerRef.current?.postMessage({
      type: 'START',
      offset: state.elapsed,
      mode: state.timerMode,
      total: state.pomodoroDuration * 60,
    })
    dispatch({ type: 'SET_TIMER_STATE', timerState: 'running' })
  }, [state.elapsed, state.timerMode, dispatch])

  const pause = useCallback(() => {
    workerRef.current?.postMessage({ type: 'PAUSE' })
    dispatch({ type: 'SET_TIMER_STATE', timerState: 'paused' })
  }, [dispatch])

  const reset = useCallback(() => {
    workerRef.current?.postMessage({ type: 'RESET' })
    startTimestampRef.current = null
    dispatch({ type: 'SET_TIMER_STATE', timerState: 'idle' })
    dispatch({ type: 'SET_ELAPSED', elapsed: 0 })
  }, [dispatch])

  const getStartTimestamp = useCallback(() => startTimestampRef.current, [])

  return { start, pause, reset, getStartTimestamp }
}
