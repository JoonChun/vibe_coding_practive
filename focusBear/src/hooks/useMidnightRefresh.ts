// src/hooks/useMidnightRefresh.ts
import { useEffect } from 'react'

export function useMidnightRefresh() {
  useEffect(() => {
    const now = new Date()
    const midnight = new Date(now)
    midnight.setDate(midnight.getDate() + 1)
    midnight.setHours(0, 0, 0, 0)
    const msUntilMidnight = midnight.getTime() - now.getTime()

    const id = setTimeout(() => {
      window.location.reload()
    }, msUntilMidnight)

    return () => clearTimeout(id)
  }, [])
}
