import { Routes, Route } from 'react-router-dom';
import { moduleRoutes } from './modules.js';
import Navbar from './components/Navbar.jsx';
import HomePage from './components/HomePage.jsx';
import NotFoundPage from './components/NotFoundPage.jsx';

export default function App() {
  return (
    <div className="is-flex is-flex-direction-column" style={{ minHeight: '100vh' }}>
      <Navbar />

      <main className="is-flex-grow-1">
        <Routes>
          <Route path="/" element={<HomePage />} />
          {moduleRoutes.map(r => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>

      <footer className="footer">
        <div className="content has-text-centered">
          <p>WebTemplate</p>
        </div>
      </footer>
    </div>
  );
}
