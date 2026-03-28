// src/App.tsx
import { AppProvider, useApp } from './context/AppContext'
import { Layout } from './components/layout/Layout'
import { DashboardView } from './components/dashboard/DashboardView'
import { CalendarView } from './components/calendar/CalendarView'
import { StatsView } from './components/stats/StatsView'
import { SettingsView } from './components/settings/SettingsView'

function PageRouter() {
  const { state } = useApp()
  switch (state.currentPage) {
    case 'dashboard': return <DashboardView />
    case 'calendar': return <CalendarView />
    case 'stats': return <StatsView />
    case 'settings': return <SettingsView />
  }
}

export default function App() {
  return (
    <AppProvider>
      <Layout>
        <PageRouter />
      </Layout>
    </AppProvider>
  )
}
