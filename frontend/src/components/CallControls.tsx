import type { CallStatus } from '../realtime/session'

const STATUS_TEXT: Record<CallStatus, string> = {
  idle: 'Start a call and just talk.',
  connecting: 'Connecting…',
  listening: 'Listening',
  'user-speaking': 'Hearing you…',
  thinking: 'Thinking…',
  'assistant-speaking': 'Speaking',
}

interface Props {
  status: CallStatus
  latenciesMs: number[]
  onStart: () => void
  onStop: () => void
}

export function CallControls({ status, latenciesMs, onStart, onStop }: Props) {
  const inCall = status !== 'idle'
  const last = latenciesMs.at(-1)
  const median = latenciesMs.length > 0 ? medianOf(latenciesMs) : undefined

  return (
    <section className="card call" aria-label="Call">
      <div className={`orb orb-${status}`} aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </div>
      <p className="status" role="status" aria-live="polite">
        {STATUS_TEXT[status]}
      </p>
      <button
        type="button"
        className={inCall ? 'danger' : 'primary'}
        onClick={inCall ? onStop : onStart}
      >
        {inCall ? 'End call' : 'Start call'}
      </button>
      {last !== undefined && (
        <p className="latency" title="From the end of your speech to the first sound of the reply">
          Reply delay: <strong>{last} ms</strong>
          {latenciesMs.length > 1 && <> · median {median} ms over {latenciesMs.length}</>}
        </p>
      )}
    </section>
  )
}

function medianOf(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : Math.round((sorted[middle - 1] + sorted[middle]) / 2)
}
