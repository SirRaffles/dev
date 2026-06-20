import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Keep Vite's dep-scan and fs access OUT of backend/ — its venv contains
  // gradio's prebuilt Svelte source which Vite tries to bundle and fails on.
  optimizeDeps: {
    entries: ['index.html', 'src/**/*.{ts,tsx,js,jsx}'],
  },
  server: {
    port: 3000,
    fs: {
      deny: ['backend/**', '**/venv/**', '**/.venv/**'],
    },
    proxy: {
      '/transcribe': 'http://localhost:8000',
      '/job': 'http://localhost:8000',
      '/batch': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/models': 'http://localhost:8000',
      '/process': 'http://localhost:8000',
      '/refine': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/contexts': 'http://localhost:8000',
      '/speakers': 'http://localhost:8000',
      '/calls': 'http://localhost:8000',
      '/jpr': 'http://localhost:8000',
      '/learning': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'build',
    sourcemap: false,
  },
  test: {
    environment: 'node',
    include: ['src/**/*.test.ts'],
  },
});
