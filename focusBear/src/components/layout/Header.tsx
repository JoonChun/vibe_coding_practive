import { useApp } from '../../context/AppContext'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { useEffect } from 'react'

function formatSeconds(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m`
  return `${s}s`
}

const PAGE_TITLES: Record<string, string> = {
  dashboard: 'Dashboard',
  calendar: 'Flow Map',
  stats: 'Growth Stats',
  settings: 'Settings',
}

export function Header() {
  const { state } = useApp()
  const { undo, redo } = useUndoRedo()

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) { e.preventDefault(); undo() }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) { e.preventDefault(); redo() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  return (
    <header className="fixed top-0 left-0 md:left-64 right-0 h-14 bg-[#fbf9f5]/80 dark:bg-[#0F172A]/80 backdrop-blur-xl border-b border-outline-variant/20 dark:border-white/5 flex items-center px-6 gap-4 z-10">
      <h2 className="text-sm font-mono uppercase tracking-widest text-primary dark:text-[#00FF41] font-bold md:block hidden">
        {PAGE_TITLES[state.currentPage] ?? 'FocusBear'}
      </h2>
      <span className="text-lg font-bold text-primary dark:text-[#00FF41] md:hidden">🐻 FocusBear</span>

      {state.todayTotal > 0 && (
        <span className="font-mono text-xs text-on-surface-variant">
          오늘 <strong className="text-primary dark:text-[#00FF41]">{formatSeconds(state.todayTotal)}</strong> 집중
        </span>
      )}
    </header>
  )
}
