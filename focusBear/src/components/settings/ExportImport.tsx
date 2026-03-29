// src/components/settings/ExportImport.tsx
import { Download, Upload } from 'lucide-react'
import { db } from '../../db/schema'
import type { Session } from '../../types'

async function exportJSON() {
  const sessions = await db.sessions.toArray()
  const categories = await db.categories.toArray()
  const blob = new Blob(
    [JSON.stringify({ sessions, categories, exportedAt: new Date().toISOString() }, null, 2)],
    { type: 'application/json' }
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `focusbear-backup-${new Date().toISOString().split('T')[0]}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function exportCSV() {
  const sessions = await db.sessions.toArray()
  const header = 'id,start,end,duration,category,memo,isManual'
  const rows = sessions.map(s =>
    [s.id, s.start, s.end, s.duration, `"${s.category}"`, `"${s.memo}"`, s.isManual].join(',')
  )
  const csv = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `focusbear-sessions-${new Date().toISOString().split('T')[0]}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

async function importJSON(file: File) {
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    if (!data.sessions || !Array.isArray(data.sessions)) throw new Error('Invalid format')
    await db.transaction('rw', db.sessions, db.categories, async () => {
      await db.sessions.clear()
      await db.categories.clear()
      const sessions = data.sessions.map(({ id: _, ...s }: Session) => s)
      await db.sessions.bulkAdd(sessions)
      if (data.categories) {
        const cats = data.categories.map(({ id: _, ...c }: { id: number; name: string; color: string }) => c)
        await db.categories.bulkAdd(cats)
      }
    })
    alert('복구 완료! 페이지를 새로고침합니다.')
    location.reload()
  } catch {
    alert('파일 형식이 올바르지 않습니다.')
  }
}

export function ExportImport() {
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <button
          onClick={exportJSON}
          className="flex items-center gap-2 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          <Download size={14} /> JSON 내보내기
        </button>
        <button
          onClick={exportCSV}
          className="flex items-center gap-2 px-4 py-2 rounded-xl border border-gray-200 dark:border-gray-700 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
        >
          <Download size={14} /> CSV 내보내기
        </button>
      </div>

      <label className="flex items-center gap-2 px-4 py-2 rounded-xl border border-dashed border-gray-300 dark:border-gray-600 text-sm cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors w-fit">
        <Upload size={14} />
        JSON 복구
        <input
          type="file"
          accept=".json"
          className="hidden"
          onChange={e => e.target.files?.[0] && importJSON(e.target.files[0])}
        />
      </label>
    </div>
  )
}
