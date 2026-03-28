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
