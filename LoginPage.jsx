import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch {
      setError('Email or password is incorrect.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-ink px-4">
      <div className="w-full max-w-sm">
        <p className="mb-1 font-display text-2xl font-semibold text-paper">MPLADS Risk Intelligence</p>
        <p className="mb-8 text-sm text-slate-light">SIH26102 — sign in to continue</p>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-sm bg-paper-raised p-6">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate" htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-sm border border-hairline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
              placeholder="district.lucknow@sih26102.gov.in"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate" htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-sm border border-hairline bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
              placeholder="••••••••"
            />
          </div>

          {error && <p className="text-sm text-risk-critical">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-sm bg-ink py-2 text-sm font-medium text-paper transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-xs text-slate-light">
          Risk scores are review priorities, not findings of fraud or guilt. Final decisions rest with authorized officers.
        </p>
      </div>
    </div>
  )
}
