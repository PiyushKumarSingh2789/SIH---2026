import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-paper">
        <p className="font-mono text-sm text-slate">Checking session…</p>
      </div>
    )
  }

  if (!user) return <Navigate to="/login" replace />

  return children
}
