// src/components/calendar/DayDetail.tsx
import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import { getSessions } from '../../db/sessions'
import type { Session } from '../../types'

function formatTime(ms: number): string {
  const d = new Date(ms)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}시간 ${m}분`
  return `${m}분`
}

interface Props {
  date: Date | null
  onClose: () => void
}

export function DayDetail({ date, onClose }: Props) {
  const [sessions, setSessions] = useState<Session[]>([])

  useEffect(() => {
    if (!date) return
    getSessions(date).then(setSessions)
  }, [date])

  return (
    <AnimatePresence>
      {date && (
        <motion.aside
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="fixed right-0 top-14 h-[calc(100vh-3.5rem)] w-80 bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-700 shadow-xl z-20 flex flex-col"
        >
          <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800">
            <h3 className="font-bold">
              {date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' })}
            </h3>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {sessions.length === 0 ? (
              <p className="text-sm text-gray-400 text-center mt-8">기록이 없습니다 🐻</p>
            ) : (
              sessions.map(s => (
                <div key={s.id} className="rounded-xl bg-gray-50 dark:bg-gray-800 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-mono text-gray-400">
                      {formatTime(s.start)} — {formatTime(s.end)}
                    </span>
                    <span className="text-xs font-medium text-[var(--accent-color)]">
                      {formatDuration(s.duration)}
                    </span>
                  </div>
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-300">{s.category}</p>
                  {s.memo && (
                    <p className="text-xs text-gray-500 mt-1 leading-relaxed">{s.memo}</p>
                  )}
                </div>
              ))
            )}
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
