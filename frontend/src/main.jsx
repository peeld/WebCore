import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import 'bulma/css/bulma.min.css';
import './index.css';
import App from './App.jsx';
import { CoreProvider } from './contexts/CoreContext.jsx';
import { moduleProviders } from './modules.js';

// Sentry and logger must be initialised before React renders.
import { initSentry, captureError, captureWarning, addBreadcrumb, setSentryUser, clearSentryUser } from './utils/sentry.js';
import { initLogger } from './utils/logger.js';

initSentry();

initLogger({
  captureError,
  captureWarning,
  addBreadcrumb,
  setUser:   setSentryUser,
  clearUser: clearSentryUser,
});

// Wrap children in each provider exported by installed modules.
// The list is built inside-out so the first provider in the array is outermost.
function ModuleProviders({ children }) {
  return moduleProviders.reduceRight(
    (acc, Provider) => <Provider>{acc}</Provider>,
    children
  );
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <CoreProvider>
        <ModuleProviders>
          <App />
        </ModuleProviders>
      </CoreProvider>
    </BrowserRouter>
  </StrictMode>,
);
