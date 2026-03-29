import { LayoutDashboard, Calendar, BarChart2, Settings, PawPrint, Sun, Moon, Undo2, Redo2, Zap } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { useTheme } from '../../hooks/useTheme'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { clsx } from 'clsx'
import type { Page } from '../../types'

const NAV_ITEMS: { page: Page; icon: React.ReactNode; label: string }[] = [
  { page: 'dashboard', icon: <LayoutDashboard size={18} />, label: 'Dashboard' },
  { page: 'calendar', icon: <Calendar size={18} />, label: 'Flow Map' },
  { page: 'stats', icon: <BarChart2 size={18} />, label: 'Growth Stats' },
  { page: 'settings', icon: <Settings size={18} />, label: 'Settings' },
]

export function Sidebar() {
  const { state, dispatch } = useApp()
  const { toggle } = useTheme()
  const { undo, redo, canUndo, canRedo } = useUndoRedo()

  const isRunning = state.timerState === 'running'

  return (
    <aside className="fixed left-0 top-0 h-full flex-col p-4 z-40 bg-[#fbf9f5] dark:bg-[#0F172A] w-64 hidden md:flex">
      {/* Brand */}
      <div className="mb-8 px-2 flex items-center gap-3">
        <div className="w-9 h-9 honey-gradient rounded-xl flex items-center justify-center text-white flex-shrink-0">
          <PawPrint size={16} />
        </div>
        <div>
          <h1 className="text-lg font-bold text-primary dark:text-[#00FF41] leading-tight">FocusBear</h1>
          <p className="font-mono text-[9px] uppercase tracking-widest text-primary/50 dark:text-[#00FF41]/50">Digital Sanctuary</p>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-1">
        {NAV_ITEMS.map(({ page, icon, label }) => (
          <button
            key={page}
            onClick={() => dispatch({ type: 'SET_PAGE', page })}
            className={clsx(
              'w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 text-left',
              state.currentPage === page
                ? 'bg-[#6c2f00]/10 dark:bg-[#00FF41]/10 text-primary dark:text-[#00FF41] translate-x-1 font-semibold'
                : 'text-primary-container dark:text-slate-400 hover:translate-x-1'
            )}
          >
            {icon}
            <span className="font-mono text-xs uppercase tracking-widest">{label}</span>
          </button>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-outline-variant/15 dark:border-white/5 pt-4 space-y-2">
        {isRunning ? (
          <div className="flex items-center gap-2 px-4 py-2 bg-[#6c2f00]/10 dark:bg-[#00FF41]/10 rounded-lg">
            <div className="w-2 h-2 bg-primary dark:bg-[#00FF41] rounded-full animate-pulse" />
            <span className="font-mono text-xs text-primary dark:text-[#00FF41] uppercase tracking-widest">집중 중...</span>
          </div>
        ) : (
          <button
            onClick={() => dispatch({ type: 'SET_PAGE', page: 'dashboard' })}
            className="honey-gradient text-white w-full py-2.5 rounded-xl font-bold text-xs uppercase tracking-wide flex items-center justify-center gap-2 active:scale-95 transition-transform"
          >
            <Zap size={14} />
            Focus Start
          </button>
        )}

        <div className="flex items-center justify-between px-2">
          <div className="flex gap-1">
            <button onClick={undo} disabled={!canUndo} title="실행 취소 (Ctrl+Z)"
              className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-container-high dark:hover:bg-white/5 disabled:opacity-30 transition-colors">
              <Undo2 size={16} />
            </button>
            <button onClick={redo} disabled={!canRedo} title="다시 실행 (Ctrl+Y)"
              className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-container-high dark:hover:bg-white/5 disabled:opacity-30 transition-colors">
              <Redo2 size={16} />
            </button>
          </div>
          <button onClick={toggle} title="테마 전환"
            className="p-2 rounded-lg text-on-surface-variant hover:bg-surface-container-high dark:hover:bg-white/5 transition-colors">
            {state.theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          </button>
        </div>
      </div>
    </aside>
  )
}
