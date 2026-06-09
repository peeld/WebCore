/**
 * utils/sentry.js
 *
 * Centralised Sentry error reporting initialisation and helper API.
 *
 * Usage
 * ─────
 * Call initSentry() once at the top of main.jsx before React renders.
 * Import helpers in any component or utility that needs to report errors.
 * Never import @sentry/react directly in application code — all Sentry
 * interaction goes through this module.
 *
 * Logging tiers
 * ─────────────
 * CRITICAL  → captureError()    Sentry level 'error'
 * WARNING   → captureWarning()  Sentry level 'warning'
 * INFO/DEBUG → console only — high-frequency, low-severity events must
 *              never be sent to Sentry to avoid quota exhaustion.
 *
 * Environment variables
 * ─────────────────────
 * VITE_SENTRY_DSN          (required in non-dev environments)
 * VITE_ENV                 ('production' | 'staging' | 'development')
 * VITE_RELEASE_VERSION     (optional, set by CI pipeline)
 */

import * as Sentry from '@sentry/react'

const DSN         = import.meta.env.VITE_SENTRY_DSN
const ENVIRONMENT = import.meta.env.VITE_ENV ?? import.meta.env.MODE
const RELEASE     = import.meta.env.VITE_RELEASE_VERSION
const IS_DEV      = ENVIRONMENT === 'development'

// ─── Initialisation ───────────────────────────────────────────────────────────

/**
 * Initialise the Sentry SDK. Must be called once, before createRoot(),
 * so that errors thrown during provider initialisation are captured.
 * Safe to call in all environments — no-op when DSN is absent.
 */
export function initSentry() {
  if (!DSN) {
    if (!IS_DEV) {
      console.error(
        '[Sentry] VITE_SENTRY_DSN is not set. ' +
        'Errors will NOT be reported. Check environment variables.'
      )
    } else {
      console.info('[Sentry] No DSN configured — disabled in development.')
    }
    return
  }

  Sentry.init({
    dsn: DSN,
    environment: ENVIRONMENT,
    release: RELEASE,
    sampleRate: IS_DEV ? 1.0 : 0.8,
    tracesSampleRate: 0,

    beforeSend(event, hint) {
      const err = hint?.originalException
      // Suppress browser extension noise and ResizeObserver quirks.
      if (err?.message?.match(/extension|chrome-extension|moz-extension/i)) return null
      if (err?.message?.match(/ResizeObserver loop/i)) return null
      // In development, surface locally rather than sending.
      if (IS_DEV) {
        console.error('[Sentry DEV] Event captured (not sent):', event)
        return null
      }
      return event
    },

    integrations: [Sentry.browserTracingIntegration()],
    sendDefaultPii: false,
  })

  console.info(`[Sentry] Initialised — env:${ENVIRONMENT} release:${RELEASE ?? 'unknown'}`)
}

// ─── User identity ────────────────────────────────────────────────────────────

/** Attach authenticated user to all subsequent Sentry events. */
export function setSentryUser(user) {
  if (!user) return
  Sentry.setUser({ id: String(user.id), username: user.username, email: user.email })
}

/** Remove user identity from Sentry on logout. */
export function clearSentryUser() {
  Sentry.setUser(null)
}

// ─── Reporting helpers ────────────────────────────────────────────────────────

/** Report a critical error that requires developer action. */
export function captureError(error, context = {}, contextKey = 'extra') {
  Sentry.withScope(scope => {
    scope.setLevel('error')
    scope.setContext(contextKey, context)
    Sentry.captureException(error)
  })
}

/** Report a warning-level event that may indicate a systemic issue over time. */
export function captureWarning(message, context = {}) {
  Sentry.withScope(scope => {
    scope.setLevel('warning')
    scope.setContext('warning_context', context)
    Sentry.captureMessage(message)
  })
}

/** Add a breadcrumb to the current Sentry scope. Does not consume error quota. */
export function addBreadcrumb(message, data = {}, level = 'info') {
  Sentry.addBreadcrumb({ message, data, level })
}
