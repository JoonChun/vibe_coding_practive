import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useApp } from '../../context/AppContext'
import { getTodayTotal } from '../../db/sessions'
import { seedDefaultCategories } from '../../db/schema'
import { getCategories } from '../../db/categories'
import { NavGuardModal, useNavGuard } from './NavGuardModal'
import { LayoutDashboard, Calendar, BarChart2, Settings } from 'lucide-react'
import { clsx } from 'clsx'
import type { Page } from '../../types'

const MOBILE_NAV: { page: Page; icon: React.ReactNode; label: string }[] = [
  { page: 'dashboard', icon: <LayoutDashboard size={20} />, label: '홈' },
  { page: 'calendar', icon: <Calendar size={20} />, label: '지도' },
  { page: 'stats', icon: <BarChart2 size={20} />, label: '통계' },
  { page: 'settings', icon: <Settings size={20} />, label: '설정' },
]

export function Layout({ children }: { children: ReactNode }) {
  const { state, dispatch } = useApp()
  const { pendingPage, setPendingPage, handleNav: handleMobileNav } = useNavGuard()

  useEffect(() => {
    seedDefaultCategories()
      .then(() => getCategories())
      .then(cats => dispatch({ type: 'SET_CATEGORIES', categories: cats }))
      .catch(err => console.error('Failed to initialize categories:', err))
    getTodayTotal()
      .then(total => dispatch({ type: 'SET_TODAY_TOTAL', total }))
      .catch(err => console.error('Failed to load today total:', err))
  }, [dispatch])

  return (
    <div className="min-h-screen bg-[var(--bg-color)]">
      <Header />
      <Sidebar />
      <main className="md:ml-64 pt-14 pb-20 md:pb-0 min-h-screen">
        {children}
      </main>
      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 w-full z-50 bg-[#fbf9f5]/80 dark:bg-[#0F172A]/80 backdrop-blur-xl border-t border-outline-variant/20 dark:border-white/5 flex justify-around items-center py-2 px-4">
        {MOBILE_NAV.map(({ page, icon, label }) => (
          <button
            key={page}
            onClick={() => handleMobileNav(page)}
            className={clsx(
              'flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-colors text-xs font-mono',
              state.currentPage === page
                ? 'text-primary dark:text-[#00FF41]'
                : 'text-on-surface-variant'
            )}
          >
            {icon}
            <span className="text-[10px] uppercase tracking-wide">{label}</span>
          </button>
        ))}
      </nav>
      <NavGuardModal
        pendingPage={pendingPage}
        timerState={state.timerState}
        onConfirm={(page) => { dispatch({ type: 'SET_PAGE', page }); setPendingPage(null) }}
        onCancel={() => setPendingPage(null)}
      />
    </div>
  )
}
