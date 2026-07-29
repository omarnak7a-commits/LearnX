import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  /** Label shown in the fallback UI so it's obvious which part of the
   * page failed (e.g. "My Files"), instead of a generic blank/black screen. */
  boundaryName: string
  /** Optional: reset the crashed subtree without a full page reload. */
  onReset?: () => void
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Isolates rendering crashes to the subtree that actually failed instead
 * of letting them propagate up and unmount the entire React application.
 *
 * ROOT CAUSE this exists to fix: prior to this component, LearnX had NO
 * error boundary anywhere in the tree. A single uncaught exception
 * thrown during render — anywhere, by anything — would unmount the
 * whole app back to the bare `<div id="root">`, leaving only the raw
 * `<body>` background visible. In dark mode that background
 * (`--background: #0A0D14`) is visually indistinguishable from solid
 * black, which is exactly what the "My Files black screen" bug looked
 * like: a real render-time TypeError (see
 * `src/lib/fileVault/migrations.ts` for the specific defect that
 * triggered it) with no boundary to catch it.
 *
 * This does not replace fixing the actual root cause of any given
 * crash — it's the last line of defense so that *the next* unexpected
 * render error degrades to a small, in-place recovery card instead of
 * silently blacking out a student's entire dashboard.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Surface the real error to the console (never swallow it) so it's
    // debuggable — this boundary isolates the crash visually, it never
    // hides that a bug happened.
    console.error(
      `[${this.props.boundaryName}] Rendering error caught by ErrorBoundary:`,
      error,
      info.componentStack
    )
  }

  private handleReset = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.error) {
      return (
        <div
          className="glass-card p-8 flex flex-col items-center text-center gap-3"
          style={{ color: 'var(--foreground)' }}
        >
          <span className="text-3xl">⚠️</span>
          <p className="text-sm font-semibold">{this.props.boundaryName} hit an unexpected error</p>
          <p className="text-xs max-w-sm" style={{ color: 'var(--muted-foreground)' }}>
            {this.state.error.message}
          </p>
          <button
            onClick={this.handleReset}
            className="text-xs font-semibold px-4 py-2 rounded-lg mt-1"
            style={{ background: 'var(--primary)', color: 'var(--primary-foreground)' }}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
