// src/db/schema.ts
import Dexie, { type Table } from 'dexie'
import type { Session, Category, Setting } from '../types'

export class FocusBearDB extends Dexie {
  sessions!: Table<Session>
  categories!: Table<Category>
  settings!: Table<Setting>

  constructor() {
    super('FocusBearDB')
    this.version(1).stores({
      sessions: '++id, start, end, category',
      categories: '++id, name',
      settings: 'key',
    })
  }
}

export const db = new FocusBearDB()

// 앱 최초 실행 시 기본 카테고리 시드
export async function seedDefaultCategories() {
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
}
