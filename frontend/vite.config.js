import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Allows module api.js files to import from '@core/frontend/api'
      // without publishing the core package to npm.
      '@core/frontend': path.resolve(__dirname, './src'),
    },
    // Ensure all workspace modules share a single React instance.
    dedupe: ['react', 'react-dom', 'react-router-dom', '@react-oauth/google'],
  },
  server: {
    proxy: {
      // Forward all /api/ requests to Django during development.
      // Eliminates CORS issues without needing django-cors-headers in dev.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
