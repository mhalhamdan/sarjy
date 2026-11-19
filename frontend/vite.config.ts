import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In development the API runs separately on :8000. Proxying keeps everything on one origin,
// as it is in production, so the session cookie works without any cross-origin setup.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
