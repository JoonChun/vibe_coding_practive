// src/components/calendar/CalendarView.tsx
import { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight, Clock, Flame } from 'lucide-react'
import { HeatmapCell } from './HeatmapCell'
import { DayDetail } from './DayDetail'
import { getSessionsByRange, getMonthSummary } from '../../db/sessions'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function getDaysInMonth(year: number, month: number): Date[] {
  const first = new Date(year, month, 1)
  const last = new Date(year, month + 1, 0)
  const days: Date[] = []

  for (let i = 0; i < first.getDay(); i++) {
    days.push(new Date(year, month, -first.getDay() + 1 + i))
  }
  for (let d = 1; d <= last.getDate(); d++) {
    days.push(new Date(year, month, d))
  }
  while (days.length < 42) {
    const lastDay = days[days.length - 1]
    days.push(new Date(lastDay.getFullYear(), lastDay.getMonth(), lastDay.getDate() + 1))
  }
  return days
}

function formatFocusTime(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  if (h > 0 && m > 0) return `${h}h ${m}m`
  if (h > 0) return `${h}h`
  return `${m}m`
}

export function CalendarView() {
  const today = new Date()
  const [viewYear, setViewYear] = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)
  const [sessionMap, setSessionMap] = useState<Map<string, number>>(new Map())
  const [monthSummary, setMonthSummary] = useState<{ totalSeconds: number; sessionCount: number }>({
    totalSeconds: 0,
    sessionCount: 0,
  })

  const days = getDaysInMonth(viewYear, viewMonth)

  useEffect(() => {
    const allDays = getDaysInMonth(viewYear, viewMonth)
    const from = allDays[0].getTime()
    const to = allDays[allDays.length - 1].getTime() + 86400000
    getSessionsByRange(from, to).then(sessions => {
      const map = new Map<string, number>()
      for (const s of sessions) {
        const key = new Date(s.start).toDateString()
        map.set(key, (map.get(key) ?? 0) + s.duration)
      }
      setSessionMap(map)
    })
    getMonthSummary(viewYear, viewMonth).then(setMonthSummary)
  }, [viewYear, viewMonth])

  function prevMonth() {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  function nextMonth() {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }

  const isCurrentViewMonth = viewYear === today.getFullYear() && viewMonth === today.getMonth()

  function handleDayClick(day: Date) {
    setSelectedDay(prev =>
      prev && prev.toDateString() === day.toDateString() ? null : day
    )
  }

  return (
    <div className="p-6 md:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header: month title + navigation + monthly stats */}
      <section className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
        <div>
          <p className="font-mono text-xs text-primary dark:text-[#00FF41] tracking-widest uppercase mb-1">
            {isCurrentViewMonth ? 'Current Journey' : 'Past Journey'}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={prevMonth}
              className="p-2 rounded-full hover:bg-primary/10 dark:hover:bg-[#00FF41]/10 active:scale-95 transition-all text-primary dark:text-[#00FF41]"
              aria-label="Previous month"
            >
              <ChevronLeft size={20} />
            </button>
            <h3 className="text-3xl md:text-4xl font-extrabold font-headline text-primary dark:text-[#00FF41] tracking-tighter">
              {MONTH_NAMES[viewMonth]} {viewYear}
            </h3>
            <button
              onClick={nextMonth}
              className="p-2 rounded-full hover:bg-primary/10 dark:hover:bg-[#00FF41]/10 active:scale-95 transition-all text-primary dark:text-[#00FF41]"
              aria-label="Next month"
            >
              <ChevronRight size={20} />
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-3 items-start md:items-end">
          {/* Monthly stats chips */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2 bg-surface-container-low dark:bg-gray-800 px-4 py-2.5 rounded-xl shadow-fur">
              <Clock size={16} className="text-primary dark:text-[#00FF41]" />
              <span className="font-mono text-sm font-bold text-primary dark:text-[#00FF41]">
                {formatFocusTime(monthSummary.totalSeconds)}
              </span>
              <span className="font-mono text-xs text-outline uppercase tracking-wider">focus</span>
            </div>
            <div className="flex items-center gap-2 bg-surface-container-low dark:bg-gray-800 px-4 py-2.5 rounded-xl shadow-fur">
              <Flame size={16} className="text-primary dark:text-[#00FF41]" />
              <span className="font-mono text-sm font-bold text-primary dark:text-[#00FF41]">
                {monthSummary.sessionCount}
              </span>
              <span className="font-mono text-xs text-outline uppercase tracking-wider">sessions</span>
            </div>
          </div>

          {/* DULL → SHARP legend */}
          <div className="flex items-center gap-2 bg-surface-container-low dark:bg-gray-800 px-4 py-2 rounded-xl">
            <span className="font-mono text-xs text-outline uppercase tracking-wider">Dull</span>
            <div className="flex gap-1">
              <div className="w-4 h-4 rounded-sm bg-surface-container-highest dark:bg-gray-700" />
              <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: 'rgba(108,47,0,0.15)' }} />
              <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: 'rgba(108,47,0,0.35)' }} />
              <div className="w-4 h-4 rounded-sm" style={{ backgroundColor: 'rgba(108,47,0,0.65)' }} />
              <div className="w-4 h-4 rounded-sm bg-primary dark:bg-[#00FF41]" />
            </div>
            <span className="font-mono text-xs text-outline uppercase tracking-wider">Sharp</span>
          </div>
        </div>
      </section>

      {/* Calendar grid */}
      <div className="bg-surface-container-low dark:bg-gray-900 p-4 md:p-6 rounded-4xl shadow-fur">
        {/* Day-of-week headers */}
        <div className="grid grid-cols-7 mb-2">
          {WEEKDAYS.map(d => (
            <div key={d} className="text-center py-2">
              <span className="font-mono text-xs text-outline dark:text-gray-500 uppercase tracking-widest">{d}</span>
            </div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 gap-1.5 md:gap-2">
          {days.map((day, i) => (
            <HeatmapCell
              key={i}
              date={day}
              totalSeconds={sessionMap.get(day.toDateString()) ?? 0}
              isToday={day.toDateString() === today.toDateString()}
              isCurrentMonth={day.getMonth() === viewMonth}
              isSelected={selectedDay !== null && day.toDateString() === selectedDay.toDateString()}
              onClick={() => handleDayClick(day)}
            />
          ))}
        </div>
      </div>

      {/* Day detail slide panel */}
      <DayDetail date={selectedDay} onClose={() => setSelectedDay(null)} />
    </div>
  )
}
