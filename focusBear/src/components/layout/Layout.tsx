// src/components/layout/Layout.tsx
import { useEffect } from 'react'
import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { useApp } from '../../context/AppContext'
import { getTodayTotal } from '../../db/sessions'
import { seedDefaultCategories } from '../../db/schema'

export function Layout({ children }: { children: ReactNode }) {
  const { dispatch } = useApp()

  useEffect(() => {
    seedDefaultCategories()
    getTodayTotal().then(total => dispatch({ type: 'SET_TODAY_TOTAL', total }))
  }, [dispatch])

  return (
    <div className="min-h-screen bg-[var(--bg-color)]">
      <Header />
      <Sidebar />
      <main className="ml-16 pt-14 min-h-screen">
        {children}
      </main>
    </div>
  )
}
