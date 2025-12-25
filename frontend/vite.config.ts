import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  const API_URL = env.VITE_API_URL || 'http://localhost:8000'
  const port = Number(env.VITE_PORT) || 3000

  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: port,
      proxy: {
        '/api': {
          target: API_URL,
          changeOrigin: true
        }
      }
    }
  }
})
