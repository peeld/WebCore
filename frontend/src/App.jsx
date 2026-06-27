import { Routes, Route } from 'react-router-dom';
import { moduleRoutes } from './modules.js';
import Navbar from './components/Navbar.jsx';
import AdminPage from './components/AdminPage.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import HomePage from './components/HomePage.jsx';
import UserPage from './components/UserPage.jsx';
import NotFoundPage from './components/NotFoundPage.jsx';
import PrivateRoute from './components/PrivateRoute.jsx';

export default function App() {
  return (
    <div className="is-flex is-flex-direction-column" style={{ minHeight: '100vh' }}>
      <Navbar />

      <main className="is-flex-grow-1">
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<PrivateRoute><UserPage /></PrivateRoute>} />
            <Route path="/admin" element={<PrivateRoute><AdminPage /></PrivateRoute>} />
            {moduleRoutes.map(r => (
              <Route key={r.path} path={r.path} element={r.element} />
            ))}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ErrorBoundary>
      </main>

      <footer className="footer">
        <div className="content has-text-centered">
          <p>WebTemplate</p>
        </div>
      </footer>
    </div>
  );
}
