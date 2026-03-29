// src/components/layout/Header.tsx
import { Sun, Moon, Undo2, Redo2 } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { useTheme } from '../../hooks/useTheme'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { useEffect } from 'react'

function formatSeconds(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}시간 ${m}분`
  if (m > 0) return `${m}분`
  return `${s}초`
}

export function Header() {
  const { state } = useApp()
  const { toggle } = useTheme()
  const { undo, redo, canUndo, canRedo } = useUndoRedo()

  // 키보드 단축키
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault()
        redo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [undo, redo])

  return (
    <header className="fixed top-0 left-16 right-0 h-14 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700 flex items-center px-6 gap-4 z-10">
      <span className="text-xl font-bold text-[var(--accent-color)] select-none">🐻 FocusBear</span>

      {state.todayTotal > 0 && (
        <span className="text-sm text-gray-500 dark:text-gray-400">
          오늘 <strong className="text-[var(--accent-color)]">{formatSeconds(state.todayTotal)}</strong> 집중
        </span>
      )}

      <div className="ml-auto flex items-center gap-2">
        <button
          onClick={undo}
          disabled={!canUndo}
          title="실행 취소 (Ctrl+Z)"
          className="p-2 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
        >
          <Undo2 size={18} />
        </button>
        <button
          onClick={redo}
          disabled={!canRedo}
          title="다시 실행 (Ctrl+Y)"
          className="p-2 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 transition-colors"
        >
          <Redo2 size={18} />
        </button>

        <button
          onClick={toggle}
          title="다크모드 전환"
          className="p-2 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {state.theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>
      </div>
    </header>
  )
}
