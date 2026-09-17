// Consistent loading/error/empty/permission states used across every page, so the app never
// shows a raw "Loading...", "undefined", or a blank screen while something is in flight or absent.

export function Skeleton({ className = '' }) {
  return <div className={`animate-skeleton rounded-sm bg-hairline ${className}`} />
}

export function LoadingState({ label = 'Loading' }) {
  return (
    <div className="flex flex-col gap-2 px-8 py-8">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong.', onRetry }) {
  return (
    <div className="rounded-sm border border-risk-critical bg-risk-critical-bg px-5 py-6 text-sm text-risk-critical">
      <p>{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-sm border border-risk-critical px-3 py-1.5 text-xs font-medium hover:bg-white"
        >
          Retry
        </button>
      )}
    </div>
  )
}

export function PermissionDeniedState({ message = "You don't have access to this." }) {
  return (
    <div className="rounded-sm border border-hairline bg-paper-raised px-5 py-6 text-sm text-slate">
      <p className="font-medium text-ink">Access restricted</p>
      <p className="mt-1">{message}</p>
    </div>
  )
}

export function EmptyState({ title = 'Nothing here yet', description }) {
  return (
    <div className="rounded-sm border border-hairline bg-paper-raised px-5 py-8 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {description && <p className="mt-1 text-sm text-slate">{description}</p>}
    </div>
  )
}

/** Resolves a React Query error into one of the states above -- the one place that logic lives. */
export function QueryStateHandler({ isLoading, error, data, onRetry, emptyCheck, emptyState, children }) {
  if (isLoading) return <LoadingState />
  if (error) {
    if (error.response?.status === 403) {
      return <PermissionDeniedState message="This is outside your assigned scope." />
    }
    if (error.response?.status === 401) {
      return <PermissionDeniedState message="Your session has expired. Please sign in again." />
    }
    return <ErrorState message={error.response?.data?.detail || 'Could not load this data.'} onRetry={onRetry} />
  }
  if (emptyCheck ? emptyCheck(data) : !data) {
    return emptyState || <EmptyState />
  }
  return children
}
