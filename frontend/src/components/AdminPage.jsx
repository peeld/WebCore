import { Link } from 'react-router-dom';
import { moduleAdminCards } from '../modules.js';

export default function AdminPage() {
  return (
    <section className="section">
      <div className="container">
        <h1 className="title">Admin</h1>
        {moduleAdminCards.length === 0 ? (
          <p className="has-text-grey">No modules have registered admin cards.</p>
        ) : (
          <div className="columns is-multiline">
            {moduleAdminCards.map((card, i) => (
              <div key={i} className="column is-one-third">
                <div className="card">
                  <header className="card-header">
                    <p className="card-header-title">{card.title}</p>
                  </header>
                  {card.description && (
                    <div className="card-content">
                      <p className="content">{card.description}</p>
                    </div>
                  )}
                  {card.links?.length > 0 && (
                    <footer className="card-footer">
                      {card.links.map((link, j) => (
                        <Link key={j} to={link.to} className="card-footer-item">
                          {link.label}
                        </Link>
                      ))}
                    </footer>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
