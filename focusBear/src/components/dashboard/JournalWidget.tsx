// src/components/dashboard/JournalWidget.tsx
import { useEffect, useState } from 'react'
import { BookOpen } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { getJournalEntry, todayDateString } from '../../db/journals'
import type { JournalEntry } from '../../types'

export function JournalWidget() {
  const { dispatch } = useApp()
  const [entry, setEntry] = useState<JournalEntry | null>(null)

  useEffect(() => {
    getJournalEntry(todayDateString()).then(e => setEntry(e ?? null))
  }, [])

  const goToJournal = () => dispatch({ type: 'SET_PAGE', page: 'journal' })

  return (
    <button
      onClick={goToJournal}
      className="w-full max-w-sm text-left bg-surface-container-low dark:bg-white/5 rounded-4xl fur-shadow px-6 py-4 hover:opacity-80 transition-opacity"
    >
      <div className="flex items-center gap-2 mb-2">
        <BookOpen size={14} className="text-primary dark:text-[#00FF41]" />
        <span className="font-mono text-[10px] uppercase tracking-widest text-primary/60 dark:text-[#00FF41]/60">
          오늘의 일지
        </span>
      </div>
      {entry?.did ? (
        <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2 leading-relaxed">
          {entry.did}
        </p>
      ) : (
        <p className="text-xs text-gray-400 dark:text-gray-600">
          오늘 하루를 기록해보세요 →
        </p>
      )}
    </button>
  )
}
