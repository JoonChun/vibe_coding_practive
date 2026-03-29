// src/components/calendar/ManualSessionDialog.tsx
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import type { Category } from '../../types'

interface Props {
  open: boolean
  date: Date
  categories: Category[]
  initialSession?: { start: number; end: number; category: string; memo: string }
  onSave: (start: number, end: number, category: string, memo: string) => void
  onClose: () => void
}

function toLocalTimeString(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function parseTime(date: Date, timeStr: string): number {
  const [h, m] = timeStr.split(':').map(Number)
  const d = new Date(date)
  d.setHours(h, m, 0, 0)
  return d.getTime()
}

export function ManualSessionDialog({ open, date, categories, initialSession, onSave, onClose }: Props) {
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('10:00')
  const [category, setCategory] = useState('')
  const [memo, setMemo] = useState('')
  const [error, setError] = useState('')

  const isEditMode = !!initialSession

  useEffect(() => {
    if (categories.length > 0 && !category) setCategory(categories[0].name)
  }, [categories, category])

  useEffect(() => {
    if (open) {
      if (initialSession) {
        setStartTime(toLocalTimeString(new Date(initialSession.start)))
        setEndTime(toLocalTimeString(new Date(initialSession.end)))
        setCategory(initialSession.category)
        setMemo(initialSession.memo)
      } else {
        const now = new Date()
        const isToday = date.toDateString() === now.toDateString()
        if (isToday) {
          setEndTime(toLocalTimeString(now))
          setStartTime(toLocalTimeString(new Date(now.getTime() - 60 * 60 * 1000)))
        } else {
          setStartTime('09:00')
          setEndTime('10:00')
        }
        setMemo('')
        if (categories.length > 0) setCategory(categories[0].name)
      }
      setError('')
    }
  }, [open, date, initialSession, categories])

  function handleSave() {
    const start = parseTime(date, startTime)
    const end = parseTime(date, endTime)
    if (end <= start) {
      setError('종료 시간은 시작 시간보다 늦어야 합니다.')
      return
    }
    if (!category) {
      setError('카테고리를 선택해주세요.')
      return
    }
    onSave(start, end, category, memo)
    onClose()
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <motion.div
            initial={{ scale: 0.9, y: 20 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.9, y: 20 }}
            className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-sm shadow-2xl"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-lg">{isEditMode ? '✏️ 기록 수정' : '⏱ 수동 기록 추가'}</h2>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <p className="text-sm text-gray-500 mb-4">
              {date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' })}
            </p>

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className="flex-1">
                  <label className="text-xs text-gray-500 mb-1 block">시작</label>
                  <input
                    type="time"
                    value={startTime}
                    onChange={e => { setStartTime(e.target.value); setError('') }}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
                  />
                </div>
                <span className="text-gray-400 mt-5">—</span>
                <div className="flex-1">
                  <label className="text-xs text-gray-500 mb-1 block">종료</label>
                  <input
                    type="time"
                    value={endTime}
                    onChange={e => { setEndTime(e.target.value); setError('') }}
                    className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
                  />
                </div>
              </div>

              {error && <p className="text-xs text-red-500">{error}</p>}

              <div>
                <label className="text-xs text-gray-500 mb-1 block">카테고리</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
                >
                  {categories.map(c => (
                    <option key={c.id} value={c.name}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-500 mb-1 block">메모 (선택)</label>
                <textarea
                  value={memo}
                  onChange={e => setMemo(e.target.value)}
                  placeholder="무엇을 했나요?"
                  rows={3}
                  className="w-full px-3 py-2 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
                />
              </div>
            </div>

            <div className="flex gap-2 mt-4">
              <button
                onClick={onClose}
                className="flex-1 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleSave}
                disabled={categories.length === 0}
                className="flex-1 py-2 rounded-xl bg-[var(--accent-color)] text-white text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {isEditMode ? '수정 완료' : '추가하기'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
