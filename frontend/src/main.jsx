import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import 'bulma/css/bulma.min.css';
import './index.css';
import App from './App.jsx';
import { CoreProvider } from './contexts/CoreContext.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <CoreProvider>
        <App />
      </CoreProvider>
    </BrowserRouter>
  </StrictMode>,
);
