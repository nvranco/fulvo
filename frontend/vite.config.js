import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// El front le pide todo a /api y el servidor de Vite lo reenvía a la API de
// FastAPI, sacándole el prefijo. Así el navegador ve un solo origen y no hace
// falta configurar CORS en el backend: la API no se toca para la demo.
// FULVO_API permite apuntar a otra API (por ejemplo, la del deploy).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.FULVO_API ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (ruta) => ruta.replace(/^\/api/, ''),
      },
    },
  },
})
