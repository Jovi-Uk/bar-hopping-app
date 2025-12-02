import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Vite configuration for the Bar Hopping Optimizer frontend
// Vite is a fast build tool that provides hot module replacement during development
export default defineConfig({
  plugins: [react()],
  
  server: {
    port: 5173,
    open: true
  },
  
  build: {
    outDir: 'dist',
    sourcemap: false
  }
})
