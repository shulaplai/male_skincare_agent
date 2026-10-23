import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import os from 'node:os'

// Vite 5.4.8+ 會擋未知 Host（回 403 `Blocked request. This host ... is not allowed`）。
// 手機經 Tailscale 用 MagicDNS 名入嚟就會中 —— 用 IP 就冇事，所以好易誤診成「Tailscale 壞」。
// 唔用 `allowedHosts: true`：dev server 會變成 DNS rebinding 嘅目標。
// 只放自己嘅機名＋自己 tailnet 嘅後綴（dot 前綴 = 連子網域一齊比對）。
const HOSTNAME = os.hostname() // e.g. "LaideMac-mini.local"
const SHORT = HOSTNAME.replace(/\.local$/i, '') // Vite 逐字比對大小寫，所以原樣同細寫都要放
const LOWER = SHORT.toLowerCase()
// Tailscale 嘅 DNSName 係 sanitize 過嘅 label（唔一定等於機名），所以另外用 env 補。
const ALIASES = (process.env.VITE_HOST_ALIASES ?? 'laimac-mini').split(',').filter(Boolean)
const TAILNET = process.env.VITE_TAILNET_SUFFIX ?? 'tail7c16db.ts.net'
const ALLOWED_HOSTS = [SHORT, LOWER, `${SHORT}.local`, `${LOWER}.local`, ...ALIASES, `.${TAILNET}`]

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: ALLOWED_HOSTS,
    proxy: {
      '/api': 'http://localhost:8001',
      // The Settings connection test calls `/health`, which is NOT under `/api`.
      // nginx proxies it in the Docker path, but Vite did not — so the indicator
      // read "✗ 連唔到" in exactly the dev flow the README documents.
      '/health': 'http://localhost:8001',
    },
  },
})
