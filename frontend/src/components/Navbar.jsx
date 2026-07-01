import { useState, useEffect, useRef } from 'react';
import { NavLink } from 'react-router-dom';
import { moduleNavItems, moduleNavbarEnd } from '../modules.js';
import { useAuth } from '@modules/userauth';
import './Navbar.css';

export const NAV_ICON = import.meta.env.VITE_NAV_ICON ?? null

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user } = useAuth();
  const brandRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    function onClickOutside(e) {
      if (brandRef.current && !brandRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [menuOpen]);

  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)');
    function onWiden(e) {
      if (e.matches) setMenuOpen(false);
    }
    mq.addEventListener('change', onWiden);
    return () => mq.removeEventListener('change', onWiden);
  }, []);

  const navLinks = [
    ...(user?.is_staff ? [{ path: '/admin', label: 'Admin' }] : []),
    ...moduleNavItems.filter(item => !item.requiresAuth || user),
  ];

  return (
    <nav className="navbar is-primary" role="navigation" aria-label="main navigation">
      <div className="navbar-brand" ref={brandRef}>
        <NavLink className="navbar-item" to="/">

            { NAV_ICON ? (
              <img src={NAV_ICON} alt="" />
            ) : (
               <strong>PeelDev</strong>
            ) }


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

        {menuOpen && (
          <div className="navbar-mobile-dropdown has-text-centered" role="menu" onClick={() => setMenuOpen(false)}>
            {navLinks.map(item => (
               <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `navbar-mobile-item${isActive ? ' is-active' : ''}`
                }
              >
                {item.label}
              </NavLink>
            ))}
            {moduleNavbarEnd.length > 0 && navLinks.length > 0 && (
              <hr className="navbar-mobile-divider" />
            )}
            {moduleNavbarEnd.map((NavbarEnd, i) => (
              <div key={i} className="navbar-mobile-end-item">
                <NavbarEnd />
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="navbar-menu">
        <div className="navbar-start">
          {user?.is_staff && (
            <NavLink
              to="/admin"
              className={({ isActive }) => `navbar-item${isActive ? ' is-active' : ''}`}
            >
              Admin
            </NavLink>
          )}
          {moduleNavItems.filter(item => !item.requiresAuth || user).map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `navbar-item${isActive ? ' is-active' : ''}`}
            >
              {item.label}
            </NavLink>
          ))}
        </div>

        {moduleNavbarEnd.length > 0 && (
          <div className="navbar-end">
            {moduleNavbarEnd.map((NavbarEnd, i) => (
              <NavbarEnd key={i} />
            ))}
          </div>
        )}
      </div>
    </nav>
  );
}
