// src/hooks/useJournalReminder.ts
import { useEffect } from 'react'
import { getJournalEntry, todayDateString } from '../db/journals'

export function useJournalReminder() {
  useEffect(() => {
    if (!('Notification' in window)) return

    const reminderTimeStr = localStorage.getItem('journalReminderTime') ?? '21:00'
    const enabled = localStorage.getItem('journalReminderEnabled') !== 'false'
    if (!enabled) return

    const [hh, mm] = reminderTimeStr.split(':').map(Number)
    const now = new Date()
    const reminder = new Date()
    reminder.setHours(hh, mm, 0, 0)

    // 이미 지난 시각이면 스케줄하지 않음
    if (reminder <= now) return

    const msUntil = reminder.getTime() - now.getTime()

    const id = setTimeout(async () => {
      if (Notification.permission !== 'granted') {
        console.warn('useJournalReminder: notification permission not granted')
        return
      }
      const today = todayDateString()
      const entry = await getJournalEntry(today)
      if (!entry?.did) {
        const n = new Notification('🐻 FocusBear', {
          body: '오늘 일지를 아직 작성하지 않았어요 📔',
        })
        n.onclick = () => {
          window.focus()
        }
      }
    }, msUntil)

    return () => clearTimeout(id)
  }, [])
}
