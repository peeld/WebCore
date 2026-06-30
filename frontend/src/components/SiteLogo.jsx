/**
 * SiteLogo.jsx — Site name/logo display component.
 * Reads APP_NAME from the environment; falls back to 'App'.
 * Used in auth pages and the Navbar.
 */

export const SITE_NAME = import.meta.env.VITE_APP_NAME ?? 'App'
export const SITE_ICON = import.meta.env.VITE_APP_ICON ?? null

/** Renders the site name as a styled inline element. */
export default function SiteLogo({ className = '', style = {} }) {
  return (
    <span className={`has-text-weight-bold ${className}`} style={style}>
      {SITE_ICON && <p><img src={SITE_ICON} /></p>}
      {SITE_NAME}
    </span>
  )
}
