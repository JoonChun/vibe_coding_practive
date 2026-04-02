// src/db/journals.ts
import { db } from './schema'
import type { JournalEntry } from '../types'

export function todayDateString(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export async function getJournalEntry(date: string): Promise<JournalEntry | undefined> {
  return db.journals.where('date').equals(date).first()
}

export async function upsertJournalEntry(entry: Omit<JournalEntry, 'id'>): Promise<void> {
  const existing = await db.journals.where('date').equals(entry.date).first()
  if (existing?.id !== undefined) {
    await db.journals.update(existing.id, { ...entry, updatedAt: Date.now() })
  } else {
    await db.journals.add({ ...entry, updatedAt: Date.now() })
  }
}

export async function getJournalDates(): Promise<string[]> {
  const all = await db.journals.orderBy('date').reverse().toArray()
  return all.map(e => e.date)
}
