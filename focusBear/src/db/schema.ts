// src/db/schema.ts
import Dexie, { type Table } from 'dexie'
import type { Session, Category, Setting, JournalEntry } from '../types'

export class FocusBearDB extends Dexie {
  sessions!: Table<Session>
  categories!: Table<Category>
  settings!: Table<Setting>
  journals!: Table<JournalEntry>

  constructor() {
    super('FocusBearDB')
    this.version(1).stores({
      sessions: '++id, start, end, category',
      categories: '++id, name',
      settings: 'key',
    })
    this.version(2).stores({
      sessions: '++id, start, end, category',
      categories: '++id, name',
      settings: 'key',
      journals: '++id, &date',
    })
  }
}

export const db = new FocusBearDB()

let _seedPromise: Promise<void> | null = null

export async function seedDefaultCategories(): Promise<void> {
  if (_seedPromise) return _seedPromise
  _seedPromise = (async () => {
    const count = await db.categories.count()
    if (count === 0) {
      await db.categories.bulkAdd([
        { name: '개발', color: '#3B82F6' },
        { name: '독서', color: '#10B981' },
        { name: '공부', color: '#F59E0B' },
        { name: '운동', color: '#EF4444' },
        { name: '기타', color: '#8B5CF6' },
      ])
    }
  })().finally(() => { _seedPromise = null })
  return _seedPromise
}
