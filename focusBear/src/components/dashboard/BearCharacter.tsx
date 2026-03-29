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

// StudyBear: bear at a desk with book, laptop, pencil
function StudyBear({ animationEnabled }: { animationEnabled: boolean }) {
  return (
    <div className="flex flex-col items-center select-none">
      <motion.div
        animate={animationEnabled ? { y: [0, -3, 0] } : { y: 0 }}
        transition={{ repeat: Infinity, duration: 3, ease: 'easeInOut' }}
        className="flex flex-col items-center"
      >
        <div className="text-6xl leading-none mb-1">🐻</div>
        {/* Desk props */}
        <div className="flex items-end justify-center gap-1.5 mb-0.5">
          <span className="text-xl">📖</span>
          <div className="w-14 h-9 bg-slate-800 dark:bg-slate-700 rounded-sm flex items-center justify-center shadow-sm border border-slate-600">
            <span className="font-mono text-[8px] text-green-400 leading-none tracking-tighter">{'> _'}</span>
          </div>
          <span className="text-lg">✏️</span>
        </div>
        {/* Desk surface */}
        <div className="w-36 h-1.5 bg-amber-800/60 dark:bg-amber-900/60 rounded-full shadow-sm" />
      </motion.div>
    </div>
  )
}

// HoneyBear: bear eating honey with animation
function HoneyBear({ animationEnabled }: { animationEnabled: boolean }) {
  return (
    <div className="flex flex-col items-center select-none">
      <div className="relative">
        {/* Nom nom text */}
        <motion.span
          className="absolute -top-3 -right-1 text-[11px] font-bold text-amber-700 dark:text-amber-400 font-mono"
          animate={animationEnabled ? { scale: [0.8, 1.2, 0.8], opacity: [0.5, 1, 0.5] } : {}}
          transition={{ repeat: Infinity, duration: 0.7 }}
        >
          냠냠
        </motion.span>
        {/* Bear with honey */}
        <motion.div
          animate={animationEnabled ? { rotate: [-6, 6, -6] } : { rotate: 0 }}
          transition={{ repeat: Infinity, duration: 0.9, ease: 'easeInOut' }}
          className="text-6xl leading-none text-center"
        >
          🐻
        </motion.div>
        <motion.div
          animate={animationEnabled ? { y: [0, -4, 0], rotate: [0, 8, 0] } : {}}
          transition={{ repeat: Infinity, duration: 1, ease: 'easeInOut' }}
          className="text-4xl leading-none text-center mt-1"
        >
          🍯
        </motion.div>
      </div>
    </div>
  )
}

// SleepBear: bear sleeping on bed with zzz's
function SleepBear({ animationEnabled }: { animationEnabled: boolean }) {
  return (
    <div className="flex flex-col items-center select-none">
      <div className="relative">
        {/* Floating zzz's */}
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="absolute font-mono font-bold text-blue-400 dark:text-blue-300 select-none"
            style={{
              fontSize: `${0.65 + i * 0.22}rem`,
              right: `${-6 - i * 13}px`,
              top: `${-6 - i * 11}px`,
            }}
            animate={animationEnabled ? { y: [0, -10, 0], opacity: [0.9, 0.1, 0.9] } : {}}
            transition={{ repeat: Infinity, duration: 2.2, delay: i * 0.55, ease: 'easeInOut' }}
          >
            z
          </motion.span>
        ))}
        <div className="text-6xl leading-none text-center">🐻</div>
        {/* Bed */}
        <div className="text-4xl leading-none text-center -mt-2">🛏️</div>
      </div>
    </div>
  )
}

export function BearCharacter({ mood, elapsed, timerMode, timerState, animationEnabled, pomodoroDuration }: Props) {
  const isFocus = mood === 'focus'
  const isRunning = timerState === 'running'

  const pomodoroProgress = timerMode === 'pomodoro'
    ? Math.min(elapsed / (pomodoroDuration * 60), 1)
    : null

  return (
    <div className="flex flex-col items-center gap-4 select-none">
      <div className="relative">
        {/* MatrixCanvas: floating above only when running */}
        <AnimatePresence>
          {isRunning && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3 }}
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3"
            >
              <MatrixCanvas active={animationEnabled} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Bear scene */}
        <AnimatePresence mode="wait">
          {isRunning && (
            <motion.div key="study"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
            >
              <StudyBear animationEnabled={animationEnabled} />
            </motion.div>
          )}
          {timerState === 'paused' && (
            <motion.div key="honey"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
            >
              <HoneyBear animationEnabled={animationEnabled} />
            </motion.div>
          )}
          {timerState === 'idle' && (
            <motion.div key="sleep"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.25 }}
            >
              <SleepBear animationEnabled={animationEnabled} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Pomodoro progress bar */}
      {pomodoroProgress !== null && isFocus && (
        <div className="w-56 h-2 bg-surface-container-high dark:bg-white/10 rounded-full overflow-hidden">
          <motion.div
            className="h-full honey-gradient rounded-full"
            style={{ width: `${pomodoroProgress * 100}%` }}
          />
        </div>
      )}

      {/* Status label */}
      <p className="text-xs font-mono uppercase tracking-[0.2em] text-on-surface-variant dark:text-slate-400">
        {timerState === 'running' ? '[ 집중 중... ]'
          : timerState === 'paused' ? '[ 일시정지 중 ]'
          : '[ 쉬는 중 ]'}
      </p>
    </div>
  )
}
