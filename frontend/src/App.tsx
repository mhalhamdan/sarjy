import { useEffect, useState } from 'react'
import { api, setUnauthorizedListener } from './api'
import { Assistant } from './components/Assistant'
import { PasscodeGate } from './components/PasscodeGate'

type AuthState = 'checking' | 'authenticated' | 'anonymous'

export default function App() {
  const [auth, setAuth] = useState<AuthState>('checking')

  useEffect(() => {
    setUnauthorizedListener(() => setAuth('anonymous'))
    api
      .authStatus()
      .then(({ authenticated }) => setAuth(authenticated ? 'authenticated' : 'anonymous'))
      .catch(() => setAuth('anonymous'))
  }, [])

  if (auth === 'checking') return null
  if (auth === 'anonymous') return <PasscodeGate onAuthenticated={() => setAuth('authenticated')} />
  return <Assistant />
}
