/**
 * utils/api.js
 *
 * JWT-aware HTTP client for authenticated API calls.
 * Used by modules that need Bearer-token auth (i.e. after userauth is installed).
 *
 * Structure
 * ─────────
 * BASE / WSBASE     — validated env-var constants
 * mediaUrl()        — resolves relative media paths to absolute URLs
 * onUnauthorized()  — registers the 401 logout callback (called by AuthContext)
 * armAuthGate()     — opens the startup window (called by AuthContext)
 * releaseAuthGate() — closes it once the initial token check settles
 * apiFetch()        — authenticated fetch wrapper with error handling
 *
 * Error reporting routes through utils/logger so this module has no
 * direct dependency on Sentry (or any other reporting service).
 *
 * Auth / 401 handling
 * ───────────────────
 * apiFetch() cannot import from AuthContext without creating a circular
 * dependency. Instead, AuthContext registers a logout callback via
 * onUnauthorized() on mount. When apiFetch receives a 401 it calls that
 * callback, which runs AuthContext's logout().
 *
 * Startup gate
 * ────────────
 * On a cold load the stored access token is often already expired, and
 * AuthContext refreshes it asynchronously. Module effects (org lists,
 * featured products, ...) fire in the same tick, so without a gate they go
 * out carrying the stale token and are rejected 401 by the authentication
 * layer - even on AllowAny endpoints - which then triggers a spurious
 * logout. AuthContext arms the gate during its first render (before any
 * effect runs) and releases it once the initial token validation settles.
 * apiFetch awaits the gate, never attaches a token it can see is expired,
 * and ignores 401s while the gate is armed so that doRefresh() remains the
 * only thing that can end the session.
 */

import { captureError, captureWarning, addBreadcrumb } from './logger'

// ─── Environment validation ───────────────────────────────────────────────────

/**
 * Validates a required environment variable at module load time.
 * Throws immediately if missing so the failure is obvious at startup.
 */
function requireEnv(name, value) {
  if (value === undefined || value === null || value === 'undefined') {
    const err = new Error(`[api.js] Required environment variable ${name} is not set.`)
    captureError(err, { variable: name, mode: import.meta.env.MODE }, 'config')
    throw err
  }
  return value
}

export const BASE   = requireEnv('VITE_API_URL', import.meta.env.VITE_API_URL)
export const WSBASE = requireEnv('VITE_WS_URL',  import.meta.env.VITE_WS_URL)

// ─── Unauthorised callback ────────────────────────────────────────────────────

/**
 * Safe fallback used before AuthContext has registered its handler.
 * Clears auth keys and hard-navigates to /login.
 */
let _unauthorizedHandler = () => {
  captureWarning('401 received before AuthContext registered its handler — using fallback')
  ;['access', 'refresh', 'username', 'user_id'].forEach(k => localStorage.removeItem(k))
  window.location.href = '/login'
}

/**
 * Registers the logout function from AuthContext as the 401 handler.
 * Call this inside AuthContext's useEffect on mount.
 *
 * @param {() => void} handler
 */
export function onUnauthorized(handler) {
  _unauthorizedHandler = handler
}

// ─── Startup auth gate ────────────────────────────────────────────────────────

/** Hard cap on how long apiFetch will wait for the initial token refresh. */
const AUTH_GATE_TIMEOUT_MS = 5000

/** Clock-skew allowance when deciding whether a stored token is expired. */
const EXPIRY_SKEW_MS = 5000

let _authGateArmed   = false
let _authGateResolve = () => {}
let _authGatePromise = null

/**
 * Arms the startup gate. Called by AuthContext during its first render —
 * before any child effect runs — so that module mount-time API calls wait
 * for the initial token validation instead of racing it.
 *
 * Sites without userauth installed never call this, so whenAuthReady()
 * stays a no-op and apiFetch is unaffected.
 */
export function armAuthGate() {
  if (_authGateArmed) return
  _authGateArmed   = true
  _authGatePromise = new Promise(resolve => { _authGateResolve = resolve })
  addBreadcrumb('Auth startup gate armed', {}, 'info')
}

/**
 * Releases the startup gate. Called by AuthContext once the initial token
 * validation settles (token confirmed valid, or a refresh attempt finished).
 * Safe to call more than once.
 */
export function releaseAuthGate() {
  if (!_authGateArmed) return
  _authGateArmed = false
  _authGateResolve()
  addBreadcrumb('Auth startup gate released', {}, 'info')
}

/**
 * True while the initial token validation is still in flight.
 * apiFetch uses this to ignore 401s during startup.
 *
 * @returns {boolean}
 */
export function isAuthStarting() {
  return _authGateArmed
}

/**
 * Resolves once the gate is released, or after AUTH_GATE_TIMEOUT_MS if the
 * initial refresh hangs — a stalled auth request must not stall the app.
 *
 * @returns {Promise<void>}
 */
function whenAuthReady() {
  if (!_authGateArmed || !_authGatePromise) return Promise.resolve()
  return Promise.race([
    _authGatePromise,
    new Promise(resolve => setTimeout(() => {
      captureWarning('Auth startup gate timed out — proceeding without it')
      resolve()
    }, AUTH_GATE_TIMEOUT_MS)),
  ])
}

/**
 * Reads the exp claim from a JWT without verifying its signature.
 * Duplicated here rather than imported from userauth: core must not depend
 * on a module. Returns null if the token cannot be decoded.
 *
 * @param {string} token
 * @returns {number|null} Expiry in milliseconds since the epoch
 */
function tokenExpiryMs(token) {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const { exp } = JSON.parse(atob(parts[1]))
    return typeof exp === 'number' ? exp * 1000 : null
  } catch (_) {
    return null
  }
}

/**
 * True when the token's expiry is known and already past (minus skew).
 * An undecodable token is treated as usable — the backend is the authority.
 *
 * @param {string} token
 * @returns {boolean}
 */
function isExpired(token) {
  const exp = tokenExpiryMs(token)
  return exp !== null && exp - EXPIRY_SKEW_MS <= Date.now()
}

// ─── Media URL resolution ─────────────────────────────────────────────────────

/**
 * Resolves a media file path to an absolute URL.
 * null/undefined → null | blob: → as-is | relative → prepended with BASE
 *
 * @param {string|null} path
 * @returns {string|null}
 */
export function mediaUrl(path) {
  if (!path) return null
  if (path.startsWith('blob:')) return path
  if (path.startsWith('http'))  return path
  return `${BASE}${path.startsWith('/') ? '' : '/'}${path}`
}

// ─── Core fetch wrapper ───────────────────────────────────────────────────────

/**
 * apiFetch
 *
 * Authenticated wrapper around the browser fetch API.
 * - Waits for the startup auth gate so requests are not sent mid-refresh
 * - Injects JWT Bearer token from localStorage, unless it is already expired
 * - Omits Content-Type for FormData (browser sets the multipart boundary)
 * - 401 → calls the registered unauthorised handler (ignored during startup)
 * - 5xx → captured as a critical error via logger, response still returned
 * - 4xx (non-401) → breadcrumb added, response returned to caller
 * - Network failure → captured via logger, re-thrown as a clean Error
 *
 * @param {string}      path      - API path, e.g. '/api/userauth/login/'
 * @param {RequestInit} [options] - Standard fetch options
 * @returns {Promise<Response>}
 * @throws {Error} On network failure
 */
export async function apiFetch(path, options = {}) {
  // Wait for the initial token validation to settle, if one is in flight.
  // Resolves immediately when no gate is armed (no userauth, or startup done).
  await whenAuthReady()

  const stored = localStorage.getItem('access')

  // An expired token is worse than no token: the authentication layer rejects
  // it with a 401 before permission checks run, so public (AllowAny) endpoints
  // fail too. Send the request anonymously instead and let the caller decide.
  const token = stored && !isExpired(stored) ? stored : null
  if (stored && !token) {
    addBreadcrumb('Stored access token expired — sending request unauthenticated', { path }, 'info')
  }

  const headers = {
    ...options.headers,
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const url = `${BASE}${path}`
  addBreadcrumb(`API ${options.method ?? 'GET'} ${path}`, { url }, 'info')

  let res
  try {
    res = await fetch(url, { ...options, headers })
  } catch (networkError) {
    captureError(networkError, { path, method: options.method ?? 'GET' }, 'network')
    throw new Error(`Network error on ${options.method ?? 'GET'} ${path}: ${networkError.message}`)
  }

  if (res.status === 401) {
    // During startup the session is still being established: a 401 here means
    // this request lost the race, not that the session is dead. doRefresh() in
    // AuthContext is the only thing allowed to end the session in that window.
    if (isAuthStarting()) {
      addBreadcrumb('401 during auth startup — not clearing session', { path }, 'warning')
      return res
    }
    captureWarning('401 Unauthorised — clearing session', { path })
    _unauthorizedHandler()
    return res
  }

  if (res.status >= 500) {
    captureError(
      new Error(`API ${res.status} on ${options.method ?? 'GET'} ${path}`),
      { path, status: res.status, method: options.method ?? 'GET' },
      'api'
    )
  } else if (res.status >= 400) {
    addBreadcrumb(
      `API ${res.status} on ${path}`,
      { status: res.status, method: options.method ?? 'GET' },
      'warning'
    )
  }

  return res
}
