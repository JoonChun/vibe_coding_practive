// src/hooks/useUndoRedo.ts
import { useCallback } from 'react'
import { db } from '../db/schema'
import { useApp } from '../context/AppContext'
import type { DbAction } from '../types'

export async function applyDbAction(action: DbAction): Promise<void> {
  switch (action.type) {
    case 'ADD_SESSION': {
      await db.sessions.put(action.session)
      break
    }
    case 'DELETE_SESSION':
      if (action.session.id !== undefined) {
        await db.sessions.delete(action.session.id)
      }
      break
    case 'UPDATE_SESSION':
      await db.sessions.put(action.after)
      break
    case 'BATCH':
      for (const a of action.forward) await applyDbAction(a)
      break
  }
}

export async function applyInverseDbAction(action: DbAction): Promise<void> {
  switch (action.type) {
    case 'ADD_SESSION':
      if (action.session.id !== undefined) {
        await db.sessions.delete(action.session.id)
      }
      break
    case 'DELETE_SESSION': {
      await db.sessions.put(action.session)
      break
    }
    case 'UPDATE_SESSION':
      await db.sessions.put(action.before)
      break
    case 'BATCH':
      for (const a of [...action.backward].reverse()) await applyInverseDbAction(a)
      break
  }
}

export function useUndoRedo() {
  const { state, dispatch } = useApp()

  const record = useCallback((action: DbAction) => {
    dispatch({ type: 'PUSH_UNDO', action })
  }, [dispatch])

  const undo = useCallback(async () => {
    const action = state.undoStack[state.undoStack.length - 1]
    if (!action) return
    await applyInverseDbAction(action)
    dispatch({ type: 'UNDO' })
  }, [state.undoStack, dispatch])

  const redo = useCallback(async () => {
    const action = state.redoStack[state.redoStack.length - 1]
    if (!action) return
    await applyDbAction(action)
    dispatch({ type: 'REDO' })
  }, [state.redoStack, dispatch])

  return {
    undo,
    redo,
    record,
    canUndo: state.undoStack.length > 0,
    canRedo: state.redoStack.length > 0,
  }
}
