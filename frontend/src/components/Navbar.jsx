import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { moduleNavItems } from '../modules.js';

/**
 * Top navigation bar. Module nav items are injected from the generated manifest.
 * Handles the Bulma burger toggle for mobile viewports.
 */
export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="navbar is-primary" role="navigation" aria-label="main navigation">
      <div className="navbar-brand">
        <NavLink className="navbar-item" to="/">
          <strong>WebTemplate</strong>
        </NavLink>
        <a
          role="button"
          className={`navbar-burger ${menuOpen ? 'is-active' : ''}`}
          aria-label="Toggle navigation menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(open => !open)}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </a>
      </div>

      <div className={`navbar-menu ${menuOpen ? 'is-active' : ''}`}>
        <div className="navbar-start">
          {moduleNavItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `navbar-item${isActive ? ' is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
}
