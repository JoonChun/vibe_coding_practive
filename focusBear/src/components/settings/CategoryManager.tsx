// src/components/settings/CategoryManager.tsx
import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { useApp } from '../../context/AppContext'
import { addCategory, deleteCategory, getCategories } from '../../db/categories'

const PRESET_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
  '#EC4899', '#F97316', '#14B8A6', '#6366F1', '#84CC16',
]

export function CategoryManager() {
  const { state, dispatch } = useApp()
  const { categories } = state
  const [newName, setNewName] = useState('')
  const [newColor, setNewColor] = useState(PRESET_COLORS[0])
  const [error, setError] = useState('')

  async function handleAdd() {
    const name = newName.trim()
    if (!name) {
      setError('이름을 입력해 주세요.')
      return
    }
    if (categories.some(c => c.name === name)) {
      setError('이미 있는 카테고리입니다.')
      return
    }
    await addCategory({ name, color: newColor })
    const updated = await getCategories()
    dispatch({ type: 'SET_CATEGORIES', categories: updated })
    setNewName('')
    setNewColor(PRESET_COLORS[0])
    setError('')
  }

  async function handleDelete(id: number) {
    if (categories.length <= 1) return
    await deleteCategory(id)
    const updated = await getCategories()
    dispatch({ type: 'SET_CATEGORIES', categories: updated })
  }

  return (
    <div className="space-y-1">
      {categories.map(c => (
        <div
          key={c.id}
          className="flex items-center justify-between px-4 py-3"
        >
          <div className="flex items-center gap-3">
            <span
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: c.color }}
            />
            <span className="text-sm">{c.name}</span>
          </div>
          <button
            onClick={() => handleDelete(c.id!)}
            disabled={categories.length <= 1}
            className="text-gray-400 hover:text-red-400 disabled:opacity-20 transition-colors"
            aria-label={`${c.name} 삭제`}
          >
            <Trash2 size={14} />
          </button>
        </div>
      ))}

      <div className="px-4 py-3 border-t border-gray-100 dark:border-gray-800 space-y-2">
        <div className="flex gap-2">
          <input
            type="text"
            value={newName}
            onChange={e => { setNewName(e.target.value); setError('') }}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
            placeholder="새 카테고리"
            maxLength={20}
            className="flex-1 min-w-0 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
          />
          <button
            onClick={handleAdd}
            className="px-3 py-1.5 rounded-lg bg-[var(--accent-color)] text-white text-sm font-medium hover:opacity-90 transition-opacity shrink-0"
          >
            추가
          </button>
        </div>

        <div className="flex gap-1.5 flex-wrap">
          {PRESET_COLORS.map(color => (
            <button
              key={color}
              onClick={() => setNewColor(color)}
              className="w-6 h-6 rounded-full transition-transform hover:scale-110"
              style={{
                backgroundColor: color,
                outline: newColor === color ? `2px solid ${color}` : 'none',
                outlineOffset: '2px',
              }}
              aria-label={color}
            />
          ))}
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>
    </div>
  )
}
