// src/hooks/useMidnightRefresh.ts
import { useEffect } from 'react'

export function useMidnightRefresh() {
  useEffect(() => {
    function scheduleRefresh() {
      const now = new Date()
      const midnight = new Date()
      midnight.setHours(24, 0, 0, 0)
      const msUntilMidnight = midnight.getTime() - now.getTime()

      const id = setTimeout(() => {
        window.location.reload()
      }, msUntilMidnight)

      return id
    }

    const id = scheduleRefresh()
    return () => clearTimeout(id)
  }, [])
}
