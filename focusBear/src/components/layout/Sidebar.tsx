// src/components/layout/Sidebar.tsx
import { LayoutDashboard, Calendar, BarChart2, Settings } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import type { Page } from '../../types'
import { clsx } from 'clsx'

const TABS: { page: Page; icon: React.ReactNode; label: string }[] = [
  { page: 'dashboard', icon: <LayoutDashboard size={22} />, label: '대시보드' },
  { page: 'calendar', icon: <Calendar size={22} />, label: '몰입의 지도' },
  { page: 'stats', icon: <BarChart2 size={22} />, label: '성장 통계' },
  { page: 'settings', icon: <Settings size={22} />, label: '설정' },
]

export function Sidebar() {
  const { state, dispatch } = useApp()

  return (
    <aside className="fixed left-0 top-0 h-full w-16 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 flex flex-col items-center pt-20 pb-4 gap-2 z-10">
      {TABS.map(({ page, icon, label }) => (
        <button
          key={page}
          onClick={() => dispatch({ type: 'SET_PAGE', page })}
          title={label}
          className={clsx(
            'w-12 h-12 rounded-xl flex items-center justify-center transition-colors',
            state.currentPage === page
              ? 'bg-[var(--accent-color)] text-white'
              : 'text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-700 dark:hover:text-gray-200'
          )}
        >
          {icon}
        </button>
      ))}
    </aside>
  )
}
