// src/components/settings/SettingsView.tsx
import { useApp } from '../../context/AppContext'
import { ExportImport } from './ExportImport'
import { CategoryManager } from './CategoryManager'
import { AlertTriangle } from 'lucide-react'

export function SettingsView() {
  const { state, dispatch } = useApp()

  return (
    <div className="p-6 max-w-lg mx-auto space-y-8">
      <h2 className="text-xl font-bold">설정 ⚙️</h2>

      <section>
        <h3 className="font-semibold mb-3 text-sm text-gray-500 uppercase tracking-wide">화면</h3>
        <div className="bg-white dark:bg-gray-900 rounded-2xl divide-y divide-gray-100 dark:divide-gray-800 shadow-sm">
          <label className="flex items-center justify-between p-4 cursor-pointer">
            <div>
              <p className="font-medium text-sm">애니메이션</p>
              <p className="text-xs text-gray-400">곰 캐릭터 및 매트릭스 이펙트</p>
            </div>
            <button
              role="switch"
              aria-checked={state.animationEnabled}
              onClick={() => dispatch({ type: 'SET_ANIMATION', enabled: !state.animationEnabled })}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                state.animationEnabled ? 'bg-[var(--accent-color)]' : 'bg-gray-300 dark:bg-gray-600'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                state.animationEnabled ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </label>
        </div>
      </section>

      <section>
        <h3 className="font-semibold mb-3 text-sm text-gray-500 uppercase tracking-wide">타이머</h3>
        <div className="bg-white dark:bg-gray-900 rounded-2xl divide-y divide-gray-100 dark:divide-gray-800 shadow-sm">
          <div className="flex items-center justify-between p-4">
            <div>
              <p className="font-medium text-sm">뽀모도로 시간</p>
              <p className="text-xs text-gray-400">타이머 모드의 집중 시간 (분)</p>
            </div>
            <input
              type="number"
              min={1}
              max={120}
              value={state.pomodoroDuration}
              onChange={e => {
                const n = parseInt(e.target.value, 10)
                if (Number.isFinite(n) && n >= 1 && n <= 120) {
                  dispatch({ type: 'SET_POMODORO_DURATION', minutes: n })
                }
              }}
              className="w-16 text-center px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-color)]"
            />
          </div>
        </div>
      </section>

      <section>
        <h3 className="font-semibold mb-3 text-sm text-gray-500 uppercase tracking-wide">카테고리</h3>
        <div className="bg-white dark:bg-gray-900 rounded-2xl divide-y divide-gray-100 dark:divide-gray-800 shadow-sm">
          <CategoryManager />
        </div>
      </section>

      <section>
        <h3 className="font-semibold mb-3 text-sm text-gray-500 uppercase tracking-wide">데이터</h3>
        <div className="bg-white dark:bg-gray-900 rounded-2xl p-4 shadow-sm space-y-4">
          <ExportImport />
          <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <p className="text-xs">브라우저 캐시 삭제 시 데이터가 유실될 수 있습니다. 정기적으로 JSON 백업을 권장합니다.</p>
          </div>
        </div>
      </section>

      <section>
        <h3 className="font-semibold mb-3 text-sm text-gray-500 uppercase tracking-wide">앱 정보</h3>
        <div className="bg-white dark:bg-gray-900 rounded-2xl p-4 shadow-sm text-sm text-gray-400 space-y-1">
          <p>🐻 FocusBear v0.1.0</p>
          <p>Local-first · IndexedDB · PWA</p>
        </div>
      </section>
    </div>
  )
}
