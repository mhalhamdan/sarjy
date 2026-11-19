import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type Memory } from '../api'
import { useVoiceSession } from '../realtime/useVoiceSession'
import { CallControls } from './CallControls'
import { MemoryPanel } from './MemoryPanel'
import { Transcript } from './Transcript'

export function Assistant() {
  const [memories, setMemories] = useState<Memory[] | null>(null)
  const [memoryError, setMemoryError] = useState<string | null>(null)
  // Bumping the version refetches; a response from an older fetch is ignored.
  const [memoryVersion, setMemoryVersion] = useState(0)
  const refreshMemories = useCallback(() => setMemoryVersion((version) => version + 1), [])

  useEffect(() => {
    let current = true
    api
      .listMemories()
      .then((list) => {
        if (!current) return
        setMemories(list)
        setMemoryError(null)
      })
      .catch((error: unknown) => {
        if (!current) return
        setMemoryError(error instanceof ApiError ? error.message : 'Could not load memories.')
      })
    return () => {
      current = false
    }
  }, [memoryVersion])

  const { session, state } = useVoiceSession(refreshMemories)
  const inCall = state.status !== 'idle'

  async function deleteMemory(memory: Memory) {
    try {
      await api.deleteMemory(memory.id)
      if (inCall) {
        session.notifyMemoryDeleted(
          'The user deleted this fact from the memory panel. Treat it as forgotten and do not ' +
            `use it: [${memory.id}] ${memory.content}`,
        )
      }
    } catch (error) {
      setMemoryError(error instanceof ApiError ? error.message : 'Could not delete that fact.')
    }
    refreshMemories()
  }

  async function deleteAllMemories() {
    if (!window.confirm('Forget everything Sarjy remembers about you? This cannot be undone.')) {
      return
    }
    try {
      await api.deleteAllMemories()
      if (inCall) {
        session.notifyMemoryDeleted(
          'The user deleted all remembered facts from the memory panel. Treat everything under ' +
            '"What you remember about the user" as forgotten.',
        )
      }
    } catch (error) {
      setMemoryError(error instanceof ApiError ? error.message : 'Could not delete memories.')
    }
    refreshMemories()
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Sarjy</h1>
        <p className="muted">Talk naturally. Interrupt any time.</p>
      </header>
      {state.error && (
        <p className="error banner" role="alert">
          {state.error}
        </p>
      )}
      <div className="layout">
        <div className="main-column">
          <CallControls
            status={state.status}
            latenciesMs={state.latenciesMs}
            onStart={() => void session.start()}
            onStop={() => session.stop()}
          />
          <Transcript entries={state.transcript} />
        </div>
        <MemoryPanel
          memories={memories}
          error={memoryError}
          onDelete={(memory) => void deleteMemory(memory)}
          onDeleteAll={() => void deleteAllMemories()}
        />
      </div>
    </div>
  )
}
