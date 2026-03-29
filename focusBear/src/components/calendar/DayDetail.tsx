// src/components/calendar/DayDetail.tsx
import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Plus, Pencil } from 'lucide-react'
import { getSessions, addSession, deleteSession, getSessionsOverlapping } from '../../db/sessions'
import { useUndoRedo } from '../../hooks/useUndoRedo'
import { useApp } from '../../context/AppContext'
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
  const [editingSession, setEditingSession] = useState<Session | null>(null)
  const { record } = useUndoRedo()
  const { state } = useApp()

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
    const before = await getSessionsOverlapping(start, end)
    const session = { start, end, duration: Math.floor((end - start) / 1000), category, memo, isManual: true }
    await addSession(session)
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

  const handleEditSession = useCallback(async (
    start: number, end: number, category: string, memo: string
  ) => {
    if (!editingSession) return
    const oldSession = editingSession
    // 기존 세션 삭제 후 새 시간으로 재삽입
    await deleteSession(oldSession.id!)
    const newSession = { start, end, duration: Math.floor((end - start) / 1000), category, memo, isManual: true }
    await addSession(newSession)
    const after = await getSessionsOverlapping(start, end)
    record({
      type: 'BATCH',
      forward: [
        { type: 'DELETE_SESSION' as const, session: oldSession },
        ...after.map(s => ({ type: 'ADD_SESSION' as const, session: s })),
      ],
      backward: [
        ...after.map(s => ({ type: 'DELETE_SESSION' as const, session: s })),
        { type: 'ADD_SESSION' as const, session: oldSession },
      ],
    })
    setEditingSession(null)
    refresh()
  }, [editingSession, record, refresh])

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
                <div key={s.id} className="rounded-xl bg-gray-50 dark:bg-gray-800 p-3 group">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
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
                    <button
                      onClick={() => setEditingSession(s)}
                      title="수정"
                      className="p-1 rounded-lg text-gray-300 dark:text-gray-600 hover:text-[var(--accent-color)] hover:bg-gray-100 dark:hover:bg-gray-700 opacity-0 group-hover:opacity-100 transition-all shrink-0"
                    >
                      <Pencil size={13} />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
          {date && (
            <ManualSessionDialog
              open={dialogOpen}
              date={date}
              categories={state.categories}
              onSave={handleAddSession}
              onClose={() => setDialogOpen(false)}
            />
          )}
          {date && editingSession && (
            <ManualSessionDialog
              open={!!editingSession}
              date={date}
              categories={state.categories}
              initialSession={editingSession}
              onSave={handleEditSession}
              onClose={() => setEditingSession(null)}
            />
          )}
        </motion.aside>
      )}
    </AnimatePresence>
  )
}
