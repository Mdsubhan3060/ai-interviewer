// frontend/vite.config.js
// ============================================
// WHY VITE?
// Vite is the modern replacement for Create React App.
// It's 10-100x faster for local development because it uses
// native ES modules instead of bundling everything upfront.
//
// The proxy config is KEY:
// Instead of hitting http://localhost:8000/api/v1 from React,
// you just call /api/v1 and Vite forwards it to FastAPI.
// This also solves CORS in development (same origin to browser).
// ============================================

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      // @ = src folder shortcut
      // Instead of: import Button from '../../../components/common/Button'
      // You write:  import Button from '@/components/common/Button'
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    port: 3000,
    proxy: {
      // Any request starting with /api gets forwarded to FastAPI
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // Uncomment if you need to strip the /api prefix:
        // rewrite: (path) => path.replace(/^\/api/, '')
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: false, // Set to true for debugging production issues
  },
})
