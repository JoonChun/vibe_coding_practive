// src/types/index.ts
export type Page = 'dashboard' | 'calendar' | 'stats' | 'settings' | 'journal'
export type Theme = 'light' | 'dark'
export type TimerState = 'idle' | 'running' | 'paused'
export type TimerMode = 'stopwatch' | 'pomodoro'
export type BearMood = 'focus' | 'rest'

export interface Session {
  id?: number
  start: number      // Unix ms
  end: number        // Unix ms
  duration: number   // 초
  category: string
  memo: string
  isManual: boolean
}

export interface Category {
  id?: number
  name: string
  color: string
}

export interface Setting {
  key: string
  value: string
}

// Undo/Redo를 위한 DB 변경 액션
export type DbAction =
  | { type: 'ADD_SESSION'; session: Session }
  | { type: 'DELETE_SESSION'; session: Session }
  | { type: 'UPDATE_SESSION'; before: Session; after: Session }
  | { type: 'BATCH'; forward: DbAction[]; backward: DbAction[] }

export interface WorkerMessage {
  type?: 'DONE' | 'TICK'
  elapsed: number
  remaining?: number
  paused?: boolean
}

export interface WorkerCommand {
  type: 'START' | 'PAUSE' | 'RESET'
  offset?: number
  mode?: TimerMode
  total?: number
}

export interface JournalEntry {
  id?: number
  date: string       // 'YYYY-MM-DD', unique
  did: string        // 오늘 한 것
  todo: string       // 내일 할 것
  memo: string       // 메모
  updatedAt: number  // Unix ms
}
