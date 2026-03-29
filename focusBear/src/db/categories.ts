// src/db/categories.ts
import { db } from './schema'
import type { Category } from '../types'

export async function getCategories(): Promise<Category[]> {
  return db.categories.toArray()
}

export async function addCategory(category: Omit<Category, 'id'>): Promise<number> {
  return db.categories.add(category)
}

export async function deleteCategory(id: number): Promise<void> {
  await db.categories.delete(id)
}

export async function getSetting(key: string): Promise<string | null> {
  const row = await db.settings.get(key)
  return row?.value ?? null
}

export async function setSetting(key: string, value: string): Promise<void> {
  await db.settings.put({ key, value })
}
