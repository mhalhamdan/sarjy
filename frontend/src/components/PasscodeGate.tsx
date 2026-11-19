import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../api'

export function PasscodeGate({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [passcode, setPasscode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.enterPasscode(passcode)
      onAuthenticated()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
      setSubmitting(false)
    }
  }

  return (
    <main className="gate">
      <form className="card gate-card" onSubmit={submit}>
        <h1>Sarjy</h1>
        <p className="muted">A voice assistant that remembers you. Enter the passcode to start.</p>
        <label htmlFor="passcode">Passcode</label>
        <input
          id="passcode"
          type="password"
          autoComplete="current-password"
          autoFocus
          value={passcode}
          onChange={(event) => setPasscode(event.target.value)}
          aria-invalid={error !== null}
          aria-describedby={error ? 'passcode-error' : undefined}
        />
        {error && (
          <p id="passcode-error" className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="primary" disabled={submitting || passcode === ''}>
          {submitting ? 'Checking…' : 'Continue'}
        </button>
      </form>
    </main>
  )
}
