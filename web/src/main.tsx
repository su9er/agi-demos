import React from 'react';

import { BrowserRouter } from 'react-router-dom';

import { QueryClientProvider } from '@tanstack/react-query';
import ReactDOM from 'react-dom/client';

import App from './App';
import { AppInitializer } from './components/common/AppInitializer';
import { queryClient } from './services/client/queryClient';
import './index.css';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppInitializer>
          <App />
        </AppInitializer>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
