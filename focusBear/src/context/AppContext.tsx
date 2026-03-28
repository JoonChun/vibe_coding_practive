// src/context/AppContext.tsx
import React, { createContext, useContext, useReducer, ReactNode } from 'react'
import type { Page, Theme, TimerState, TimerMode, BearMood, DbAction } from '../types'

export interface AppState {
  currentPage: Page
  theme: Theme
  timerState: TimerState
  timerMode: TimerMode
  bearMood: BearMood
  elapsed: number          // 초
  selectedCategory: string
  todayTotal: number       // 초
  animationEnabled: boolean
  undoStack: DbAction[]
  redoStack: DbAction[]
}

export type AppAction =
  | { type: 'SET_PAGE'; page: Page }
  | { type: 'SET_THEME'; theme: Theme }
  | { type: 'SET_TIMER_STATE'; timerState: TimerState }
  | { type: 'SET_TIMER_MODE'; mode: TimerMode }
  | { type: 'SET_ELAPSED'; elapsed: number }
  | { type: 'SET_CATEGORY'; category: string }
  | { type: 'SET_TODAY_TOTAL'; total: number }
  | { type: 'SET_ANIMATION'; enabled: boolean }
  | { type: 'PUSH_UNDO'; action: DbAction }
  | { type: 'UNDO' }
  | { type: 'REDO' }

function getInitialTheme(): Theme {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark' || saved === 'light') return saved
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const initialState: AppState = {
  currentPage: 'dashboard',
  theme: getInitialTheme(),
  timerState: 'idle',
  timerMode: 'stopwatch',
  bearMood: 'rest',
  elapsed: 0,
  selectedCategory: '기타',
  todayTotal: 0,
  animationEnabled: true,
  undoStack: [],
  redoStack: [],
}

function reducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_PAGE':
      return { ...state, currentPage: action.page }
    case 'SET_THEME':
      return { ...state, theme: action.theme }
    case 'SET_TIMER_STATE':
      return {
        ...state,
        timerState: action.timerState,
        bearMood: action.timerState === 'running' ? 'focus' : 'rest',
      }
    case 'SET_TIMER_MODE':
      return { ...state, timerMode: action.mode, elapsed: 0 }
    case 'SET_ELAPSED':
      return { ...state, elapsed: action.elapsed }
    case 'SET_CATEGORY':
      return { ...state, selectedCategory: action.category }
    case 'SET_TODAY_TOTAL':
      return { ...state, todayTotal: action.total }
    case 'SET_ANIMATION':
      return { ...state, animationEnabled: action.enabled }
    case 'PUSH_UNDO':
      return {
        ...state,
        undoStack: [...state.undoStack.slice(-49), action.action],
        redoStack: [],
      }
    case 'UNDO': {
      if (!state.undoStack.length) return state
      const last = state.undoStack[state.undoStack.length - 1]
      return {
        ...state,
        undoStack: state.undoStack.slice(0, -1),
        redoStack: [...state.redoStack, last],
      }
    }
    case 'REDO': {
      if (!state.redoStack.length) return state
      const last = state.redoStack[state.redoStack.length - 1]
      return {
        ...state,
        redoStack: state.redoStack.slice(0, -1),
        undoStack: [...state.undoStack, last],
      }
    }
    default:
      return state
  }
}

const AppContext = createContext<{
  state: AppState
  dispatch: React.Dispatch<AppAction>
} | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}
