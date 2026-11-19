import { useEffect, useState, useSyncExternalStore } from 'react'
import { VoiceSession } from './session'

/** One VoiceSession for the component's lifetime, with its state as React state. */
export function useVoiceSession(onMemoryChanged: () => void) {
  const [session] = useState(() => new VoiceSession())
  const state = useSyncExternalStore(session.subscribe, session.getSnapshot)

  useEffect(() => {
    session.setMemoryChangedListener(onMemoryChanged)
  }, [session, onMemoryChanged])

  // Hang up if the component goes away mid-call.
  useEffect(() => () => session.stop(), [session])

  return { session, state }
}
