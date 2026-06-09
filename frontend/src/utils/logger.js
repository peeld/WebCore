/**
 * utils/logger.js
 *
 * Pluggable logging and error-reporting abstraction.
 * Decouples modules from any specific error-tracking service (Sentry,
 * Datadog, Bugsnag, etc.) so the same module can be dropped into a project
 * that uses a different backend — or none at all.
 *
 * Defaults
 * ────────
 * Without calling initLogger(), all functions fall back to console output.
 * captureError and captureWarning log to the console; addBreadcrumb is a
 * no-op (breadcrumbs are only meaningful inside a tracing session).
 *
 * Setup (call once at app startup, before rendering)
 * ────────────────────────────────────────────────────
 * import { initLogger } from '@core/frontend/utils/logger'
 * import { captureError, captureWarning, addBreadcrumb, setSentryUser, clearSentryUser } from '@core/frontend/utils/sentry'
 *
 * initLogger({
 *   captureError,
 *   captureWarning,
 *   addBreadcrumb,
 *   setUser:   setSentryUser,
 *   clearUser: clearSentryUser,
 * })
 *
 * Interface
 * ─────────
 * captureError(error, context, tag)   — unexpected errors; should alert on-call
 * captureWarning(message, context)    — notable but expected events (401, bad token, etc.)
 * addBreadcrumb(message, data, level) — low-noise trail of events; useful for replay
 * setUser(user)                       — attach identity to subsequent events
 * clearUser()                         — remove identity on logout
 */

// ── Default handlers (console fallbacks) ─────────────────────────────────────

let _captureError = (err, context = {}) =>
  console.error('[logger] error:', err, context)

let _captureWarning = (msg, context = {}) =>
  console.warn('[logger] warning:', msg, context)

let _addBreadcrumb = (_msg, _data, _level) => {
  // Silent by default — breadcrumbs are only useful inside a tracing session.
}

let _setUser   = (_user) => {}
let _clearUser = () => {}

// ── Configuration ─────────────────────────────────────────────────────────────

/**
 * Wire in an error-reporting backend. Call once at app startup before
 * rendering. Any handler left out keeps its default behaviour.
 *
 * @param {object} handlers
 * @param {Function} [handlers.captureError]
 * @param {Function} [handlers.captureWarning]
 * @param {Function} [handlers.addBreadcrumb]
 * @param {Function} [handlers.setUser]
 * @param {Function} [handlers.clearUser]
 */
export function initLogger({ captureError, captureWarning, addBreadcrumb, setUser, clearUser } = {}) {
  if (captureError)   _captureError   = captureError
  if (captureWarning) _captureWarning = captureWarning
  if (addBreadcrumb)  _addBreadcrumb  = addBreadcrumb
  if (setUser)        _setUser        = setUser
  if (clearUser)      _clearUser      = clearUser
}

// ── Public logger functions ───────────────────────────────────────────────────

/** Report an unexpected error. Routes to the configured handler. */
export const captureError   = (...args) => _captureError(...args)

/** Report a notable but expected event (rate limit, bad token, etc.). */
export const captureWarning = (...args) => _captureWarning(...args)

/** Record a low-noise breadcrumb for event replay / debugging. */
export const addBreadcrumb  = (...args) => _addBreadcrumb(...args)

/** Attach a user identity to subsequent events. */
export const setUser        = (...args) => _setUser(...args)

/** Remove user identity (call on logout). */
export const clearUser      = (...args) => _clearUser(...args)
