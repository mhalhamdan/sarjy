import type { Memory } from '../api'

interface Props {
  memories: Memory[] | null
  error: string | null
  onDelete: (memory: Memory) => void
  onDeleteAll: () => void
}

export function MemoryPanel({ memories, error, onDelete, onDeleteAll }: Props) {
  return (
    <section className="card memory" aria-label="Memory">
      <div className="memory-header">
        <h2>
          What Sarjy remembers
          {memories && memories.length > 0 && <span className="count">{memories.length}</span>}
        </h2>
        {memories && memories.length > 0 && (
          <button type="button" className="link danger-text" onClick={onDeleteAll}>
            Forget everything
          </button>
        )}
      </div>
      <p className="muted small">
        Facts are saved when you mention them in conversation and loaded at the start of each call.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {memories === null ? (
        <p className="muted">Loading…</p>
      ) : memories.length === 0 ? (
        <p className="muted">Nothing yet.</p>
      ) : (
        <ul className="memories">
          {memories.map((memory) => (
            <li key={memory.id} dir="auto">
              <span>{memory.content}</span>
              <button
                type="button"
                className="icon"
                onClick={() => onDelete(memory)}
                aria-label={`Forget: ${memory.content}`}
                title="Forget this"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
