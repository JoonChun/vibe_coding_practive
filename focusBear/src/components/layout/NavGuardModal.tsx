import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useApp } from '../../context/AppContext'
import type { Page, TimerState } from '../../types'

export function useNavGuard() {
  const { state, dispatch } = useApp()
  const [pendingPage, setPendingPage] = useState<Page | null>(null)

  const isActive = state.timerState === 'running' || state.timerState === 'paused'

  function handleNav(page: Page) {
    if (isActive && state.currentPage !== page) {
      setPendingPage(page)
    } else {
      dispatch({ type: 'SET_PAGE', page })
    }
  }

  return { pendingPage, setPendingPage, handleNav }
}

interface NavGuardModalProps {
  pendingPage: Page | null
  timerState: TimerState
  onConfirm: (page: Page) => void
  onCancel: () => void
}

export function NavGuardModal({ pendingPage, timerState, onConfirm, onCancel }: NavGuardModalProps) {
  return (
    <AnimatePresence>
      {pendingPage && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-white dark:bg-gray-900 rounded-2xl p-5 mx-4 shadow-xl w-full max-w-xs"
          >
            <h4 className="font-bold text-sm text-gray-800 dark:text-gray-100 mb-1">
              {timerState === 'running' ? '타이머 실행 중' : '타이머 일시정지 중'}
            </h4>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
              지금 페이지를 이동하면 현재 세션이 종료되지 않습니다. 정말 이동할까요?
            </p>
            <div className="flex gap-2">
              <button
                onClick={onCancel}
                className="flex-1 py-2 rounded-xl text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
              >
                계속 집중
              </button>
              <button
                onClick={() => onConfirm(pendingPage)}
                className="flex-1 py-2 rounded-xl text-xs font-medium bg-primary text-white hover:opacity-90 transition-opacity"
              >
                이동
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
