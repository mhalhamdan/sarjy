import { useEffect, useRef } from 'react'
import type { TranscriptEntry } from '../realtime/session'

export function Transcript({ entries }: { entries: TranscriptEntry[] }) {
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => {
    end.current?.scrollIntoView({ block: 'end', behavior: 'smooth' })
  }, [entries])

  return (
    <section className="card transcript" aria-label="Transcript">
      <h2>Conversation</h2>
      {entries.length === 0 ? (
        <p className="muted">
          Try “My favorite color is green”, then in a new call, “What’s my favorite color?” Or ask
          about today’s news or the weather.
        </p>
      ) : (
        <ol className="entries">
          {entries.map((entry) => (
            <li key={entry.id} className={`entry entry-${entry.role}`} dir="auto">
              {entry.role === 'tool' ? (
                <span className={entry.failed ? 'tool tool-failed' : 'tool'}>
                  {entry.text}
                  {entry.pending && <span className="dots" aria-hidden="true" />}
                  {entry.durationMs !== undefined && (
                    <span className="muted"> · {(entry.durationMs / 1000).toFixed(1)} s</span>
                  )}
                </span>
              ) : (
                <>
                  <span className="who">{entry.role === 'user' ? 'You' : 'Sarjy'}</span>
                  <span className="text">
                    {entry.text}
                    {entry.pending && <span className="dots" aria-hidden="true" />}
                  </span>
                </>
              )}
            </li>
          ))}
        </ol>
      )}
      <div ref={end} />
    </section>
  )
}
