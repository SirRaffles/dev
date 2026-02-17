import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/transcribe': 'http://localhost:8000',
      '/job': 'http://localhost:8000',
      '/batch': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/models': 'http://localhost:8000',
      '/process': 'http://localhost:8000',
      '/refine': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'build',
    sourcemap: false,
  },
});
