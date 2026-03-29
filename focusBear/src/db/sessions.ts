// src/db/sessions.ts
import { db } from './schema'
import type { Session } from '../types'

export async function getSessions(date?: Date): Promise<Session[]> {
  if (date) {
    const start = new Date(date)
    start.setHours(0, 0, 0, 0)
    const end = new Date(date)
    end.setHours(23, 59, 59, 999)
    return db.sessions
      .where('start')
      .between(start.getTime(), end.getTime(), true, true)
      .toArray()
  }
  return db.sessions.orderBy('start').toArray()
}

export async function getSessionsByRange(from: number, to: number): Promise<Session[]> {
  return db.sessions
    .where('start')
    .between(from, to, true, true)
    .toArray()
}

// start < rangeEnd AND end > rangeStart 인 모든 세션 (겹치는 세션 전부)
export async function getSessionsOverlapping(rangeStart: number, rangeEnd: number): Promise<Session[]> {
  const all = await db.sessions.toArray()
  return all.filter(s => s.start < rangeEnd && s.end > rangeStart)
}

export async function addSession(newSession: Omit<Session, 'id'>): Promise<Session[]> {
  const { start, end } = newSession

  // 겹치는 기존 세션 조회 (start < newEnd AND end > newStart)
  const all = await db.sessions.toArray()
  const overlapping = all.filter(s => s.start < end && s.end > start)

  const toDelete: number[] = []
  const toAdd: Omit<Session, 'id'>[] = []
  const toUpdate: Session[] = []

  for (const existing of overlapping) {
    if (existing.start >= start && existing.end <= end) {
      // Overwriting: 새 기록이 기존을 완전히 포함
      toDelete.push(existing.id!)
    } else if (existing.start < start && existing.end > end) {
      // Splitting: 새 기록이 기존 중간에 삽입
      toDelete.push(existing.id!)
      toAdd.push({
        ...existing,
        end: start,
        duration: Math.floor((start - existing.start) / 1000),
      })
      toAdd.push({
        ...existing,
        start: end,
        duration: Math.floor((existing.end - end) / 1000),
      })
    } else if (existing.start < start) {
      // Trimming 뒤: 기존의 뒤쪽이 겹침
      toUpdate.push({ ...existing, end: start, duration: Math.floor((start - existing.start) / 1000) })
    } else {
      // Trimming 앞: 기존의 앞쪽이 겹침
      toUpdate.push({ ...existing, start: end, duration: Math.floor((existing.end - end) / 1000) })
    }
  }

  await db.transaction('rw', db.sessions, async () => {
    for (const id of toDelete) await db.sessions.delete(id)
    for (const s of toUpdate) await db.sessions.put(s)
    await db.sessions.add({ ...newSession })
    for (const s of toAdd) {
      const { id: _, ...rest } = s as Session
      await db.sessions.add(rest)
    }
  })

  return overlapping
}

export async function deleteSession(id: number): Promise<void> {
  await db.sessions.delete(id)
}

export async function updateSession(session: Session): Promise<void> {
  await db.sessions.put(session)
}

export async function getTodayTotal(): Promise<number> {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const sessions = await db.sessions
    .where('start')
    .between(today.getTime(), tomorrow.getTime(), true, false)
    .toArray()
  return sessions.reduce((sum, s) => sum + s.duration, 0)
}

export async function getMonthSummary(year: number, month: number): Promise<{ totalSeconds: number; sessionCount: number }> {
  const start = new Date(year, month, 1).getTime()
  const end = new Date(year, month + 1, 1).getTime()
  const sessions = await getSessionsByRange(start, end)
  return {
    totalSeconds: sessions.reduce((s, r) => s + r.duration, 0),
    sessionCount: sessions.length,
  }
}

export async function getCurrentStreak(): Promise<number> {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  let streak = 0
  for (let i = 0; i < 365; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const next = new Date(d)
    next.setDate(d.getDate() + 1)
    const sessions = await getSessionsByRange(d.getTime(), next.getTime())
    if (sessions.length === 0) break
    streak++
  }
  return streak
}

export async function getWeeklyData(): Promise<{ day: string; minutes: number; isToday: boolean }[]> {
  const today = new Date()
  const results = await Promise.all(
    Array.from({ length: 7 }, (_, i) => {
      const d = new Date(today)
      d.setDate(today.getDate() - (6 - i))
      d.setHours(0, 0, 0, 0)
      const next = new Date(d)
      next.setDate(d.getDate() + 1)
      return getSessionsByRange(d.getTime(), next.getTime()).then(sessions => ({
        day: d.toLocaleDateString('ko-KR', { weekday: 'short' }),
        minutes: Math.floor(sessions.reduce((s, r) => s + r.duration, 0) / 60),
        isToday: i === 6,
      }))
    })
  )
  return results
}

export async function getWeekdayStats(): Promise<{ weekday: string; score: number; label: string }[]> {
  const DAYS = ['일', '월', '화', '수', '목', '금', '토']
  const LABELS = ['REST', 'BUILDING', 'BUILDING', 'PEAK FLOW', 'MAINTAINING', 'WINDING', 'REST']
  const monthAgo = Date.now() - 30 * 24 * 60 * 60 * 1000
  const sessions = await getSessionsByRange(monthAgo, Date.now())
  const totals = Array(7).fill(0)
  for (const s of sessions) {
    const wd = new Date(s.start).getDay()
    totals[wd] += s.duration
  }
  const maxTotal = Math.max(...totals, 1)
  return DAYS.map((weekday, i) => ({
    weekday,
    score: Math.round((totals[i] / maxTotal) * 100),
    label: totals[i] === 0 ? 'REST' : LABELS[i],
  }))
}
