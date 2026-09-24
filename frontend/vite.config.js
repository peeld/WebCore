import fs from 'fs'
import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Module sources live outside core/frontend (core/frontend/modules/* are
// symlinks into ../../modules), so Vite resolves their bare imports from the
// module's real path, where there is no node_modules. npm workspaces hoist
// every module's dependencies into core/frontend/node_modules; listing them
// in `dedupe` makes Vite resolve them from here instead. Read from the enabled
// modules' package.json so a module can add a dependency without editing core.
function moduleDependencies() {
  const dir = path.resolve(import.meta.dirname, 'modules')
  if (!fs.existsSync(dir)) return []
  const deps = new Set()
  for (const name of fs.readdirSync(dir)) {
    const pkgFile = path.join(dir, name, 'package.json')
    if (!fs.existsSync(pkgFile)) continue
    const pkg = JSON.parse(fs.readFileSync(pkgFile, 'utf8'))
    Object.keys(pkg.dependencies ?? {}).forEach(d => deps.add(d))
  }
  return [...deps]
}

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Allows module api.js files to import from '@core/frontend/api'
      // without publishing the core package to npm.
      '@core/frontend': path.resolve(import.meta.dirname, './src'),
    },
    // Ensure all workspace modules share a single React instance, and that
    // module dependencies resolve from core/frontend/node_modules (see above).
    dedupe: [...new Set([
      'react', 'react-dom', 'react-router-dom', '@react-oauth/google', '@stripe/stripe-js', '@stripe/react-stripe-js',
      ...moduleDependencies(),
    ])],
  },
  server: {
    fs: {
      // site/frontend/src is imported directly by modules.js (see install.py
      // generate_manifest) but lives outside core/frontend, Vite's default
      // fs root — without this the dev server 403s on it.
      allow: [path.resolve(import.meta.dirname, '../..')],
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
