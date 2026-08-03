import { NavLink } from 'react-router-dom';
import { moduleAdminCards } from '../modules.js';
import { useAuth } from '@modules/userauth';
import './AdminSidebar.css';

function slugify(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');
}

export default function AdminSidebar() {
  const { user } = useAuth();

  if (!user?.is_staff || moduleAdminCards.length === 0) return null;

  return (
    <aside className="menu admin-sidebar">
      {moduleAdminCards.map((card, i) => (
        <div key={i}>
          <p className="menu-label mt-3 mb-0">
            <NavLink to={`/${slugify(card.title)}/admin`}>{card.title}</NavLink>
          </p>
          {card.links?.length > 0 && (
            <ul className="menu-list">
              {card.links.map((link, j) => (
                <li className="mt-1" key={j}>
                  <NavLink to={link.to} className={({ isActive }) => (isActive ? 'is-active' : '')}>
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </aside>
  );
}
