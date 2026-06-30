/**
 * SiteLogo.jsx — Site name/logo display component.
 * Reads APP_NAME from the environment; falls back to 'App'.
 * Used in auth pages and the Navbar.
 */

export const SITE_NAME = import.meta.env.VITE_APP_NAME ?? 'App'
export const SITE_ICON = import.meta.env.VITE_APP_ICON ?? null
export const SITE_ICON_DARK = import.meta.env.VITE_APP_ICON_DARK ?? null

/** Renders the site name as a styled inline element. */
export default function SiteLogo({ className = '', style = {} }) {
  return (
    <span className={`has-text-weight-bold ${className}`} style={style}>
      {SITE_ICON && (
        <p className="site-logo-icon">
          <img src={SITE_ICON} className="site-logo-icon-light" alt="" />
          {SITE_ICON_DARK && (
            <img src={SITE_ICON_DARK} className="site-logo-icon-dark" alt="" />
          )}
        </p>
      )}
      {SITE_NAME}
    </span>
  )
}