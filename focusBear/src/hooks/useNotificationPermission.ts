// src/hooks/useNotificationPermission.ts
import { useEffect } from 'react'

export function useNotificationPermission() {
  useEffect(() => {
    if (!('Notification' in window)) return
    if (Notification.permission === 'default') {
      const id = setTimeout(() => {
        Notification.requestPermission()
      }, 3000)
      return () => clearTimeout(id)
    }
  }, [])
}
