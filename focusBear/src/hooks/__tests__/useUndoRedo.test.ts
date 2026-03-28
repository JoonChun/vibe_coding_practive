// src/hooks/__tests__/useUndoRedo.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import 'fake-indexeddb/auto'
import { db } from '../../db/schema'
import { applyDbAction, applyInverseDbAction } from '../useUndoRedo'
import type { DbAction, Session } from '../../types'

beforeEach(async () => {
  await db.sessions.clear()
})

const baseSession: Session = {
  id: 1,
  start: 1000,
  end: 2000,
  duration: 1,
  category: '개발',
  memo: '',
  isManual: false,
}

describe('applyDbAction', () => {
  it('ADD_SESSION: DB에 세션 추가', async () => {
    const action: DbAction = { type: 'ADD_SESSION', session: { ...baseSession, id: undefined } }
    await applyDbAction(action)
    expect(await db.sessions.count()).toBe(1)
  })

  it('DELETE_SESSION: DB에서 세션 삭제', async () => {
    const id = await db.sessions.add({ ...baseSession, id: undefined })
    const action: DbAction = { type: 'DELETE_SESSION', session: { ...baseSession, id } }
    await applyDbAction(action)
    expect(await db.sessions.count()).toBe(0)
  })
})

describe('applyInverseDbAction', () => {
  it('ADD_SESSION의 역: 삭제', async () => {
    const id = await db.sessions.add({ ...baseSession, id: undefined })
    const action: DbAction = { type: 'ADD_SESSION', session: { ...baseSession, id } }
    await applyInverseDbAction(action)
    expect(await db.sessions.count()).toBe(0)
  })

  it('DELETE_SESSION의 역: 추가', async () => {
    const action: DbAction = { type: 'DELETE_SESSION', session: { ...baseSession, id: undefined } }
    await applyInverseDbAction(action)
    expect(await db.sessions.count()).toBe(1)
  })
})
