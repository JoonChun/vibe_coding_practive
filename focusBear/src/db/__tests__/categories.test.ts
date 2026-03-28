import { describe, it, expect, beforeEach } from 'vitest'
import 'fake-indexeddb/auto'
import { db } from '../schema'
import { seedDefaultCategories } from '../schema'

describe('seedDefaultCategories', () => {
  beforeEach(async () => {
    await db.categories.clear()
  })

  it('seeds 5 default categories', async () => {
    await seedDefaultCategories()
    const count = await db.categories.count()
    expect(count).toBe(5)
  })

  it('concurrent calls do not produce duplicate categories', async () => {
    await Promise.all([seedDefaultCategories(), seedDefaultCategories()])
    const count = await db.categories.count()
    expect(count).toBe(5)
  })

  it('does not re-seed if categories already exist', async () => {
    await seedDefaultCategories()
    await seedDefaultCategories()
    const count = await db.categories.count()
    expect(count).toBe(5)
  })
})
