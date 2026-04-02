import { useState } from 'react'
import { useApp } from '../../context/AppContext'
import { ExportImport } from './ExportImport'
import { CategoryManager } from './CategoryManager'
import { AlertTriangle, Bell } from 'lucide-react'

export function SettingsView() {
  const { state, dispatch } = useApp()
  const [reminderEnabled, setReminderEnabled] = useState(
    () => localStorage.getItem('journalReminderEnabled') !== 'false'
  )
  const [reminderTime, setReminderTime] = useState(
    () => localStorage.getItem('journalReminderTime') ?? '21:00'
  )
  const [notifPermission, setNotifPermission] = useState(
    () => ('Notification' in window ? Notification.permission : 'unsupported' as const)
  )

  function handleReminderToggle() {
    const next = !reminderEnabled
    setReminderEnabled(next)
    localStorage.setItem('journalReminderEnabled', String(next))
  }

  function handleReminderTimeChange(value: string) {
    setReminderTime(value)
    localStorage.setItem('journalReminderTime', value)
  }

  async function handleRequestPermission() {
    const result = await Notification.requestPermission()
    setNotifPermission(result)
  }

  return (
    <div className="p-6 md:p-10 max-w-3xl mx-auto space-y-10">
      <header>
        <h2 className="text-3xl font-bold font-headline text-primary dark:text-[#00FF41]">Settings</h2>
        <p className="font-mono text-xs text-on-surface-variant dark:text-slate-400 mt-1 uppercase tracking-widest">System Config</p>
      </header>

      {/* Appearance */}
      <section className="space-y-3">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60">Appearance</h3>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 space-y-0 divide-y divide-outline-variant/15 dark:divide-white/5">
          <div className="flex items-center justify-between py-4 first:pt-0 last:pb-0">
            <div>
              <p className="font-semibold text-sm text-on-surface dark:text-slate-200">애니메이션</p>
              <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-0.5">이펙트</p>
            </div>
            <button
              role="switch"
              aria-checked={state.animationEnabled}
              onClick={() => dispatch({ type: 'SET_ANIMATION', enabled: !state.animationEnabled })}
              className={`relative w-12 h-6 rounded-full transition-colors ${state.animationEnabled ? 'honey-gradient' : 'bg-surface-container-highest dark:bg-white/10'
                }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${state.animationEnabled ? 'translate-x-6' : 'translate-x-0'
                }`} />
            </button>
          </div>
        </div>
      </section>

      {/* Daily Goal */}
      <section className="space-y-3">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60">Daily Goal</h3>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm text-on-surface dark:text-slate-200">하루 목표 집중 시간</p>
              <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-0.5">Paw Trail 진행도 기준</p>
            </div>
            <div className="flex items-center gap-2">
              {[60, 90, 120, 180, 240].map(m => (
                <button
                  key={m}
                  onClick={() => dispatch({ type: 'SET_DAILY_GOAL', minutes: m })}
                  className={`font-mono text-xs px-3 py-1.5 rounded-full transition-colors ${state.dailyGoal === m
                    ? 'honey-gradient text-white'
                    : 'bg-surface-container-highest dark:bg-white/10 text-on-surface-variant dark:text-slate-400'
                    }`}
                >
                  {m >= 60 ? `${m / 60}h` : `${m}m`}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Categories */}
      <section className="space-y-3">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60">Categories</h3>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6">
          <CategoryManager />
        </div>
      </section>

      {/* Notifications */}
      <section className="space-y-3">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60">Notifications</h3>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 space-y-0 divide-y divide-outline-variant/15 dark:divide-white/5">
          {/* 권한 상태 */}
          <div className="flex items-center justify-between py-4 first:pt-0">
            <div className="flex items-center gap-2">
              <Bell size={14} className="text-on-surface-variant" />
              <div>
                <p className="font-semibold text-sm text-on-surface dark:text-slate-200">알림 권한</p>
                <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-0.5">
                  {notifPermission === 'granted' ? '허용됨' : notifPermission === 'denied' ? '거부됨 (브라우저 설정에서 변경)' : notifPermission === 'unsupported' ? '미지원' : '미설정'}
                </p>
              </div>
            </div>
            {notifPermission === 'default' && (
              <button
                onClick={handleRequestPermission}
                className="font-mono text-xs px-3 py-1.5 rounded-full honey-gradient text-white"
              >
                권한 요청
              </button>
            )}
          </div>

          {/* 일지 리마인더 토글 */}
          <div className="flex items-center justify-between py-4">
            <div>
              <p className="font-semibold text-sm text-on-surface dark:text-slate-200">일지 리마인더</p>
              <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-0.5">매일 일정 시각에 일지 작성 알림</p>
            </div>
            <button
              role="switch"
              aria-checked={reminderEnabled}
              onClick={handleReminderToggle}
              className={`relative w-12 h-6 rounded-full transition-colors ${reminderEnabled ? 'honey-gradient' : 'bg-surface-container-highest dark:bg-white/10'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform ${reminderEnabled ? 'translate-x-6' : 'translate-x-0'}`} />
            </button>
          </div>

          {/* 리마인더 시각 */}
          {reminderEnabled && (
            <div className="flex items-center justify-between py-4 last:pb-0">
              <div>
                <p className="font-semibold text-sm text-on-surface dark:text-slate-200">리마인더 시각</p>
                <p className="text-xs text-on-surface-variant dark:text-slate-400 mt-0.5">기본값: 오후 9시</p>
              </div>
              <input
                type="time"
                value={reminderTime}
                onChange={e => handleReminderTimeChange(e.target.value)}
                className="font-mono text-sm bg-surface-container-highest dark:bg-white/10 text-on-surface dark:text-slate-200 border-none rounded-xl px-3 py-1.5 outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          )}
        </div>
      </section>

      {/* Data */}
      <section className="space-y-3">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60">Data Management</h3>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 space-y-4">
          <ExportImport />
          <div className="flex items-start gap-2.5 p-4 rounded-2xl bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <p className="text-xs leading-relaxed">브라우저 캐시 삭제 시 데이터가 유실될 수 있습니다. 정기적으로 JSON 백업을 권장합니다.</p>
          </div>
        </div>
      </section>

      {/* App Info */}
      <section className="space-y-3">
        <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary/60 dark:text-[#00FF41]/60">App Info</h3>
        <div className="bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow p-6 space-y-2">
          <div className="flex justify-between items-center text-sm">
            <span className="text-on-surface-variant dark:text-slate-400">Version</span>
            <span className="font-mono font-bold text-primary dark:text-[#00FF41]">v0.1.0-bear</span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-on-surface-variant dark:text-slate-400">Storage</span>
            <span className="font-mono text-on-surface-variant dark:text-slate-400">Local-first · IndexedDB · PWA</span>
          </div>
        </div>
      </section>
    </div>
  )
}
