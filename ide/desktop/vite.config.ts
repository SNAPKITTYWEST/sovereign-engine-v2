import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vite';

const packageRoot = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  base: './',
  build: {
    emptyOutDir: true,
    outDir: '_site',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      input: {
        desktop: resolve(packageRoot, 'desktop', 'index.html'),
      },
    },
    sourcemap: true,
    target: 'es2022',
  },
  server: {
    host: '127.0.0.1',
    port: 4183,
  },
  preview: {
    host: '127.0.0.1',
    port: 4183,
  },
});
