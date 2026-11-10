import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL('../static/dist', import.meta.url)),
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      input: './src/main.jsx',
      output: {
        entryFileNames: 'main.js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
});