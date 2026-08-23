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
    dedupe: ['react', 'react-dom', 'react-router-dom', '@react-oauth/google', '@stripe/stripe-js', '@stripe/react-stripe-js'],
  },
  server: {
    fs: {
      // site/frontend/src is imported directly by modules.js (see install.py
      // generate_manifest) but lives outside core/frontend, Vite's default
      // fs root — without this the dev server 403s on it.
      allow: [path.resolve(__dirname, '../..')],
    },
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
