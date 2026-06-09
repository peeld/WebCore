/**
 * Core API client — used by all modules.
 * Prefixes paths with /api/, attaches CSRF token, handles errors uniformly.
 * Import via: import { get, post } from '@core/frontend/api'
 */

/** Read the Django CSRF token from the cookie jar. */
function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

/**
 * Base request helper.
 * @param {string} method - HTTP verb
 * @param {string} path   - Path relative to /api/ (e.g. 'health/')
 * @param {object|null} body - JSON body for POST/PUT
 * @throws {ApiError} on non-2xx responses
 */
async function request(method, path, body = null) {
  const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken(),
  };

  const options = { method, headers, credentials: 'include' };
  if (body !== null) {
    options.body = JSON.stringify(body);
  }

  const response = await fetch(`/api/${path}`, options);

  if (!response.ok) {
    const error = new Error(`API ${method} /api/${path} failed with ${response.status}`);
    error.status = response.status;
    try {
      error.data = await response.json();
    } catch {
      error.data = null;
    }
    if (import.meta.env.DEV) {
      console.error('[api]', method, `/api/${path}`, response.status, error.data);
    }
    throw error;
  }

  // 204 No Content — return null rather than trying to parse an empty body.
  if (response.status === 204) return null;
  return response.json();
}

export const get  = (path)       => request('GET',    path);
export const post = (path, body) => request('POST',   path, body);
export const put  = (path, body) => request('PUT',    path, body);
export const del  = (path)       => request('DELETE', path);
