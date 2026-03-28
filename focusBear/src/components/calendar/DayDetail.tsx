// src/components/calendar/DayDetail.tsx
import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Plus } from 'lucide-react'
import { getSessions, addSession, getSessionsOverlapping } from '../../db/sessions'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { ManualSessionDialog } from './ManualSessionDialog'
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
  const [dialogOpen, setDialogOpen] = useState(false)
  const { record } = useUndoRedo()

  const refresh = useCallback(() => {
    if (!date) return
    getSessions(date).then(setSessions)
  }, [date])

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleAddSession = useCallback(async (
    start: number, end: number, category: string, memo: string
  ) => {
    // Undo를 위해 변경 전 상태 스냅샷 (겹치는 세션 전부 포함)
    const before = await getSessionsOverlapping(start, end)

    const session = { start, end, duration: Math.floor((end - start) / 1000), category, memo, isManual: true }
    await addSession(session)

    // 변경 후 상태 (새 세션 + 분할/수정된 세션들)
    const after = await getSessionsOverlapping(start, end)

    record({
      type: 'BATCH',
      forward: [
        ...before.map(s => ({ type: 'DELETE_SESSION' as const, session: s })),
        ...after.map(s => ({ type: 'ADD_SESSION' as const, session: s })),
      ],
      backward: [
        ...after.map(s => ({ type: 'DELETE_SESSION' as const, session: s })),
        ...before.map(s => ({ type: 'ADD_SESSION' as const, session: s })),
      ],
    })
    refresh()
  }, [record, refresh])

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
            <div className="flex items-center gap-1">
              <button
                onClick={() => setDialogOpen(true)}
                title="수동 기록 추가"
                className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-[var(--accent-color)] transition-colors"
              >
                <Plus size={18} />
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
                <X size={18} />
              </button>
            </div>
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
          {date && (
            <ManualSessionDialog
              open={dialogOpen}
              date={date}
              onSave={handleAddSession}
              onClose={() => setDialogOpen(false)}
            />
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
