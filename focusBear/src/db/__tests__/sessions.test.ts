// src/db/__tests__/sessions.test.ts
import { beforeEach, describe, expect, it } from 'vitest'
import 'fake-indexeddb/auto'
import { db, seedDefaultCategories } from '../schema'
import { addSession, getSessions, deleteSession } from '../sessions'
import type { Session } from '../../types'

function makeSession(start: number, end: number, extra: Partial<Session> = {}): Omit<Session, 'id'> {
  return {
    start,
    end,
    duration: Math.floor((end - start) / 1000),
    category: '개발',
    memo: '',
    isManual: true,
    ...extra,
  }
}

beforeEach(async () => {
  await db.sessions.clear()
  await db.categories.clear()
  await seedDefaultCategories()
})

describe('addSession - Smart Overlap Handling', () => {
  it('겹치지 않으면 그냥 추가', async () => {
    await addSession(makeSession(1000, 2000))
    await addSession(makeSession(3000, 4000))
    const all = await getSessions()
    expect(all).toHaveLength(2)
  })

  it('Overwriting: 새 기록이 기존을 완전히 덮으면 기존 삭제', async () => {
    await addSession(makeSession(2000, 3000))
    await addSession(makeSession(1000, 4000))
    const all = await getSessions()
    expect(all).toHaveLength(1)
    expect(all[0].start).toBe(1000)
    expect(all[0].end).toBe(4000)
  })

  it('Splitting: 새 기록이 기존 중간에 삽입되면 기존을 앞뒤로 분할', async () => {
    await addSession(makeSession(1000, 6000))
    await addSession(makeSession(3000, 4000))
    const all = await getSessions()
    expect(all).toHaveLength(3)
    const sorted = all.sort((a, b) => a.start - b.start)
    expect(sorted[0].start).toBe(1000)
    expect(sorted[0].end).toBe(3000)
    expect(sorted[1].start).toBe(3000)
    expect(sorted[1].end).toBe(4000)
    expect(sorted[2].start).toBe(4000)
    expect(sorted[2].end).toBe(6000)
  })

  it('Trimming 앞: 새 기록이 기존 앞을 덮으면 기존 시작을 뒤로', async () => {
    await addSession(makeSession(2000, 5000))
    await addSession(makeSession(1000, 3000))
    const all = await getSessions()
    expect(all).toHaveLength(2)
    const existing = all.find(s => s.start === 3000)
    expect(existing).toBeDefined()
    expect(existing!.end).toBe(5000)
  })

  it('Trimming 뒤: 새 기록이 기존 뒤를 덮으면 기존 끝을 앞으로', async () => {
    await addSession(makeSession(1000, 4000))
    await addSession(makeSession(3000, 5000))
    const all = await getSessions()
    expect(all).toHaveLength(2)
    const existing = all.find(s => s.start === 1000)
    expect(existing).toBeDefined()
    expect(existing!.end).toBe(3000)
  })
})

describe('deleteSession', () => {
  it('id로 세션 삭제', async () => {
    await addSession(makeSession(1000, 2000))
    const all = await getSessions()
    expect(all).toHaveLength(1)
    await deleteSession(all[0].id!)
    expect(await getSessions()).toHaveLength(0)
  })
})
