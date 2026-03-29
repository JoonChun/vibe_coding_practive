// src/hooks/useTheme.ts
import { useEffect } from 'react'
import { useApp } from '../context/AppContext'
import type { Theme } from '../types'

export function useTheme() {
  const { state, dispatch } = useApp()

  useEffect(() => {
    const root = document.documentElement
    if (state.theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
    localStorage.setItem('theme', state.theme)
  }, [state.theme])

  const toggle = () => {
    dispatch({
      type: 'SET_THEME',
      theme: state.theme === 'light' ? 'dark' : 'light',
    })
  }

  const setTheme = (theme: Theme) => dispatch({ type: 'SET_THEME', theme })

  return { theme: state.theme, toggle, setTheme }
}
