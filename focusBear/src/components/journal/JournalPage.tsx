// src/components/journal/JournalPage.tsx
import { useEffect, useState, useRef, useCallback } from 'react'
import { BookOpen } from 'lucide-react'
import { getJournalEntry, getJournalDates, upsertJournalEntry, todayDateString } from '../../db/journals'
import type { JournalEntry } from '../../types'

function formatDisplayDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
}

function isToday(dateStr: string): boolean {
  return dateStr === todayDateString()
}

export function JournalPage() {
  const today = todayDateString()
  const [dates, setDates] = useState<string[]>([])
  const [selectedDate, setSelectedDate] = useState<string>(today)
  const [entry, setEntry] = useState<JournalEntry>({ date: today, did: '', todo: '', memo: '', updatedAt: 0 })
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'idle'>('idle')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadDates = useCallback(async () => {
    const all = await getJournalDates()
    const withToday = all.includes(today) ? all : [today, ...all]
    setDates(withToday)
  }, [today])

  const loadEntry = useCallback(async (date: string) => {
    const found = await getJournalEntry(date)
    setEntry(found ?? { date, did: '', todo: '', memo: '', updatedAt: 0 })
  }, [])

  useEffect(() => {
    loadDates()
  }, [loadDates])

  useEffect(() => {
    loadEntry(selectedDate)
  }, [selectedDate, loadEntry])

  const handleChange = useCallback((field: 'did' | 'todo' | 'memo', value: string) => {
    setEntry(prev => ({ ...prev, [field]: value }))
    setSaveStatus('saving')
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      await upsertJournalEntry({ ...entry, [field]: value, date: selectedDate })
      setSaveStatus('saved')
      await loadDates()
      setTimeout(() => setSaveStatus('idle'), 2000)
    }, 1000)
  }, [entry, selectedDate, loadDates])

  return (
    <div className="h-[calc(100vh-3.5rem)] flex">
      {/* Left: date list */}
      <aside className="hidden md:flex w-52 flex-col border-r border-gray-100 dark:border-gray-800 bg-[#fbf9f5] dark:bg-[#0F172A] overflow-y-auto">
        <div className="px-4 py-4 border-b border-gray-100 dark:border-gray-800">
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-primary dark:text-[#00FF41]" />
            <span className="font-mono text-xs uppercase tracking-widest text-primary dark:text-[#00FF41] font-bold">Journal</span>
          </div>
        </div>
        <nav className="flex-1 py-2">
          {dates.map(date => (
            <button
              key={date}
              onClick={() => setSelectedDate(date)}
              className={`w-full text-left px-4 py-2.5 text-xs font-mono transition-colors ${
                selectedDate === date
                  ? 'bg-[#6c2f00]/10 dark:bg-[#00FF41]/10 text-primary dark:text-[#00FF41] font-semibold'
                  : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
            >
              {isToday(date) ? `${date} (오늘)` : date}
            </button>
          ))}
        </nav>
      </aside>

      {/* Right: editor */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-800">
          {/* Mobile date selector */}
          <select
            className="md:hidden text-sm font-mono bg-transparent text-primary dark:text-[#00FF41] border-none outline-none"
            value={selectedDate}
            onChange={e => setSelectedDate(e.target.value)}
          >
            {dates.map(d => (
              <option key={d} value={d}>{isToday(d) ? `${d} (오늘)` : d}</option>
            ))}
          </select>
          <h2 className="hidden md:block font-bold text-primary dark:text-[#00FF41]">
            {formatDisplayDate(selectedDate)}
          </h2>
          <span className={`text-[10px] font-mono transition-opacity ${saveStatus === 'idle' ? 'opacity-0' : 'opacity-100'} ${saveStatus === 'saved' ? 'text-green-500' : 'text-gray-400'}`}>
            {saveStatus === 'saving' ? '저장 중...' : '저장됨'}
          </span>
        </div>

        <div className="flex-1 flex flex-col gap-4 p-6 overflow-y-auto">
          {/* 오늘 한 것 — big (flex 2) */}
          <div className="flex flex-col flex-[2] min-h-0">
            <label className="text-[10px] font-mono uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">
              ✅ 오늘 한 것
            </label>
            <textarea
              className="flex-1 resize-none rounded-2xl bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/30 p-4 text-sm text-gray-700 dark:text-gray-300 placeholder-gray-300 dark:placeholder-gray-600 outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#00FF41]/20 transition-shadow"
              placeholder="오늘 집중한 것들을 기록해보세요..."
              value={entry.did}
              onChange={e => handleChange('did', e.target.value)}
            />
          </div>

          {/* 내일 할 것 + 메모 — small (flex 1) */}
          <div className="flex gap-4 flex-1 min-h-0">
            <div className="flex flex-col flex-1 min-h-0">
              <label className="text-[10px] font-mono uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">
                🎯 내일 할 것
              </label>
              <textarea
                className="flex-1 resize-none rounded-2xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10 p-3 text-sm text-gray-700 dark:text-gray-300 placeholder-gray-300 dark:placeholder-gray-600 outline-none focus:ring-2 focus:ring-primary/20 dark:focus:ring-[#00FF41]/10 transition-shadow"
                placeholder="내일 할 것..."
                value={entry.todo}
                onChange={e => handleChange('todo', e.target.value)}
              />
            </div>
            <div className="flex flex-col flex-1 min-h-0">
              <label className="text-[10px] font-mono uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">
                💭 메모
              </label>
              <textarea
                className="flex-1 resize-none rounded-2xl bg-gray-50 dark:bg-white/5 border border-gray-100 dark:border-white/10 p-3 text-sm text-gray-700 dark:text-gray-300 placeholder-gray-300 dark:placeholder-gray-600 outline-none focus:ring-2 focus:ring-primary/20 dark:focus:ring-[#00FF41]/10 transition-shadow"
                placeholder="기타 메모..."
                value={entry.memo}
                onChange={e => handleChange('memo', e.target.value)}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
