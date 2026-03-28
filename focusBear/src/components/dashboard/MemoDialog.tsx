import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'

interface Props {
  open: boolean
  duration: number   // 초
  category: string
  onSave: (memo: string) => void
  onSkip: () => void
}

function formatDuration(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}시간 ${m}분 ${sec}초`
  if (m > 0) return `${m}분 ${sec}초`
  return `${sec}초`
}

export function MemoDialog({ open, duration, category, onSave, onSkip }: Props) {
  const [memo, setMemo] = useState('')

  function handleSave() {
    onSave(memo)
    setMemo('')
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
            className="bg-white dark:bg-gray-900 rounded-2xl p-6 w-full max-w-md shadow-2xl"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-lg">🐻 집중 완료!</h2>
              <button onClick={onSkip} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <p className="text-sm text-gray-500 mb-1">
              <span className="font-medium text-[var(--accent-color)]">{category}</span>
              {' · '}{formatDuration(duration)} 집중
            </p>

            <textarea
              value={memo}
              onChange={e => setMemo(e.target.value)}
              placeholder="오늘의 짧은 회고를 남겨보세요... (선택)"
              rows={4}
              className="w-full mt-3 p-3 rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
            />

            <div className="flex gap-2 mt-4">
              <button
                onClick={onSkip}
                className="flex-1 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                건너뛰기
              </button>
              <button
                onClick={handleSave}
                className="flex-1 py-2 rounded-xl bg-[var(--accent-color)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
              >
                저장하기
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
