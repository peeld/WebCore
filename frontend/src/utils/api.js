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
 * - Injects JWT Bearer token from localStorage
 * - Omits Content-Type for FormData (browser sets the multipart boundary)
 * - 401 → calls the registered unauthorised handler
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
  const token = localStorage.getItem('access')

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
