import { motion, AnimatePresence } from 'framer-motion'
import { MatrixCanvas } from './MatrixCanvas'
import type { BearMood } from '../../types'

interface Props {
  mood: BearMood
  elapsed: number
  timerMode: string
  timerState: string
  animationEnabled: boolean
  pomodoroDuration: number
}

export function BearCharacter({ mood, elapsed, timerMode, timerState, animationEnabled, pomodoroDuration }: Props) {
  const isFocus = mood === 'focus'

  const pomodoroProgress = timerMode === 'pomodoro'
    ? Math.min(elapsed / (pomodoroDuration * 60), 1)
    : null

  return (
    <div className="flex flex-col items-center gap-4 select-none">
      <motion.div
        animate={animationEnabled && isFocus ? { y: [0, -6, 0] } : { y: 0 }}
        transition={{ repeat: Infinity, duration: 2.5, ease: 'easeInOut' }}
        className="relative"
      >
        <AnimatePresence>
          {isFocus && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3 }}
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2"
            >
              <MatrixCanvas active={isFocus && animationEnabled} />
            </motion.div>
          )}
        </AnimatePresence>

        <div className="text-[96px] text-center leading-none">
          {isFocus ? '🐻‍❄️' : '🐻'}
        </div>

        {isFocus && (
          <div className="text-center text-2xl -mt-4 animate-pulse">🕶️</div>
        )}

        {!isFocus && (
          <motion.div
            className="text-center text-3xl -mt-2"
            animate={animationEnabled ? { rotate: [-5, 5, -5] } : {}}
            transition={{ repeat: Infinity, duration: 3 }}
          >
            🍯
          </motion.div>
        )}
      </motion.div>

      {pomodoroProgress !== null && isFocus && (
        <div className="w-56 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-[var(--accent-color)] rounded-full"
            style={{ width: `${pomodoroProgress * 100}%` }}
          />
        </div>
      )}

      <p className="text-sm text-gray-500 dark:text-gray-400 font-mono">
        {timerState === 'running' ? '[ 집중 중... ]' : timerState === 'paused' ? '[ 일시정지 중 ]' : '[ 쉬는 중 🍯 ]'}
      </p>
    </div>
  )
}
