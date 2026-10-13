import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

// https://vite.dev/config/
export default defineConfig(({ command, mode }) => {
  const variables = loadEnv(mode, process.cwd(), 'VITE_');
  if (command === 'build' && variables.VITE_USE_MOCKS === 'true') {
    throw new Error('Production builds require VITE_USE_MOCKS=false. Use .env.development.local for mock development.');
  }
  return {
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  };
});
