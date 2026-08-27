import { useEffect } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import { moduleRoutes } from './modules.js';
import Navbar from './components/Navbar.jsx';
import AdminPage from './components/AdminPage.jsx';
import AdminSidebar from './components/AdminSidebar.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import HomePage from './components/HomePage.jsx';
import UserPage from './components/UserPage.jsx';
import NotFoundPage from './components/NotFoundPage.jsx';
import PrivateRoute from './components/PrivateRoute.jsx';

// Reset scroll on route changes — without it, a page navigated to from a
// scrolled-down link (e.g. a homepage "Learn more") opens mid-scroll.
function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0);
  }, [pathname, hash]);
  return null;
}

export default function App() {
  return (
    <div className="is-flex is-flex-direction-column" style={{ minHeight: '100vh' }}>
      <ScrollToTop />
      <Navbar />

      <div className="is-flex is-flex-grow-1">
        <AdminSidebar />

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
      </div>

      <footer className="footer">
        <div className="content has-text-centered">
          <p>---</p>
        </div>
      </footer>
    </div>
  );
}
