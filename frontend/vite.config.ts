import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8001',
      // The Settings connection test calls `/health`, which is NOT under `/api`.
      // nginx proxies it in the Docker path, but Vite did not — so the indicator
      // read "✗ 連唔到" in exactly the dev flow the README documents.
      '/health': 'http://localhost:8001',
    },
  },
})
