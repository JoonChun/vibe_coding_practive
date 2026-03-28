import type { WorkerCommand, WorkerMessage, TimerMode } from '../types'

let startTime: number | null = null
let pausedOffset = 0
let interval: ReturnType<typeof setInterval> | null = null
let mode: TimerMode = 'stopwatch'
let totalSeconds = 25 * 60

self.onmessage = (e: MessageEvent<WorkerCommand>) => {
  const cmd = e.data

  if (cmd.type === 'START') {
    mode = cmd.mode ?? 'stopwatch'
    totalSeconds = cmd.total ?? 25 * 60
    pausedOffset = cmd.offset ?? 0
    startTime = Date.now()

    if (interval) clearInterval(interval)
    interval = setInterval(() => {
      if (startTime === null) return
      const elapsed = pausedOffset + Math.floor((Date.now() - startTime) / 1000)

      if (mode === 'pomodoro') {
        const remaining = totalSeconds - elapsed
        const msg: WorkerMessage = { elapsed, remaining }
        self.postMessage(msg)
        if (remaining <= 0) {
          clearInterval(interval!)
          interval = null
          self.postMessage({ type: 'DONE', elapsed } as WorkerMessage)
        }
      } else {
        self.postMessage({ elapsed } as WorkerMessage)
      }
    }, 500)

  } else if (cmd.type === 'PAUSE') {
    if (interval) clearInterval(interval)
    interval = null
    if (startTime !== null) {
      pausedOffset += Math.floor((Date.now() - startTime) / 1000)
      startTime = null
    }
    self.postMessage({ paused: true, elapsed: pausedOffset } as WorkerMessage)

  } else if (cmd.type === 'RESET') {
    if (interval) clearInterval(interval)
    interval = null
    startTime = null
    pausedOffset = 0
    self.postMessage({ elapsed: 0 } as WorkerMessage)
  }
}
