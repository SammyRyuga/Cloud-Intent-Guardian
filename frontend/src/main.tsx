import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from '@/app/App';
import { env } from '@/config/env';
import '@/styles/index.css';

async function bootstrap() {
  if (import.meta.env.DEV && env.useMocks) {
    const { enableMocking } = await import('@/api/mocks/browser');
    await enableMocking();
  }

  const rootElement = document.getElementById('root');
  if (rootElement) {
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
  }
}

bootstrap();
