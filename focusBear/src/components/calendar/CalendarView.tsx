// src/components/calendar/CalendarView.tsx
import { useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { HeatmapCell } from './HeatmapCell'
import { DayDetail } from './DayDetail'
import { getSessionsByRange } from '../../db/sessions'

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토']
const LIGHT_COLORS = ['bg-gray-100', 'bg-amber-100', 'bg-amber-200', 'bg-amber-400', 'bg-amber-600']

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
    const last = days[days.length - 1]
    days.push(new Date(last.getFullYear(), last.getMonth(), last.getDate() + 1))
  }
  return days
}

export function CalendarView() {
  const today = new Date()
  const [viewYear, setViewYear] = useState(today.getFullYear())
  const [viewMonth, setViewMonth] = useState(today.getMonth())
  const [selectedDay, setSelectedDay] = useState<Date | null>(null)
  const [sessionMap, setSessionMap] = useState<Map<string, number>>(new Map())

  const days = getDaysInMonth(viewYear, viewMonth)

  useEffect(() => {
    const from = days[0].getTime()
    const to = days[days.length - 1].getTime() + 86400000
    getSessionsByRange(from, to).then(sessions => {
      const map = new Map<string, number>()
      for (const s of sessions) {
        const key = new Date(s.start).toDateString()
        map.set(key, (map.get(key) ?? 0) + s.duration)
      }
      setSessionMap(map)
    })
  }, [viewYear, viewMonth])

  function prevMonth() {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11) }
    else setViewMonth(m => m - 1)
  }
  function nextMonth() {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0) }
    else setViewMonth(m => m + 1)
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-bold">
          {viewYear}년 {viewMonth + 1}월
        </h2>
        <div className="flex gap-1">
          <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            <ChevronLeft size={18} />
          </button>
          <button
            onClick={() => { setViewYear(today.getFullYear()); setViewMonth(today.getMonth()) }}
            className="px-3 py-1 text-sm rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            오늘
          </button>
          <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
            <ChevronRight size={18} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7 mb-2">
        {WEEKDAYS.map(d => (
          <div key={d} className="text-center text-xs text-gray-400 py-1 font-medium">{d}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {days.map((day, i) => (
          <HeatmapCell
            key={i}
            date={day}
            totalSeconds={sessionMap.get(day.toDateString()) ?? 0}
            isToday={day.toDateString() === today.toDateString()}
            isCurrentMonth={day.getMonth() === viewMonth}
            onClick={() => setSelectedDay(day)}
          />
        ))}
      </div>

      <div className="flex items-center gap-2 mt-4 justify-end">
        <span className="text-xs text-gray-400">적음</span>
        {[0, 1, 2, 3, 4].map(l => (
          <div
            key={l}
            className={`w-4 h-4 rounded ${LIGHT_COLORS[l]}`}
          />
        ))}
        <span className="text-xs text-gray-400">많음</span>
      </div>

      <DayDetail date={selectedDay} onClose={() => setSelectedDay(null)} />
    </div>
  )
}
