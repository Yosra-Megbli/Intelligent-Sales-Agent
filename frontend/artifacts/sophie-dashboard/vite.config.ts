import path from 'path';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

// PORT and BASE_PATH were auto-injected by the original Replit environment.
// Outside Replit, default to a normal local dev setup (port 5173, root base path)
// while still allowing override via env vars if you deploy behind a sub-path.
const rawPort = process.env.PORT ?? '5173';

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

const basePath = process.env.BASE_PATH ?? '/';

// NOTE: the three @replit/vite-plugin-* packages (cartographer, dev-banner,
// runtime-error-modal) from the original Replit export were removed here.
// They are dev-only tooling scoped to *.replit.dev domains (they no-op
// outside Replit anyway, guarded by `process.env.REPL_ID !== undefined`),
// so keeping them only added three extra dependencies with no benefit for
// a deployment run outside Replit (this project's target). If this app is
// ever developed inside Replit again, they can be re-added following
// Replit's own docs.
export default defineConfig({
  base: basePath,
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
    dedupe: ['react', 'react-dom'],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist/public'),
    emptyOutDir: true,
  },
  server: {
    port,
    strictPort: true,
    host: '0.0.0.0',
    allowedHosts: true,
    fs: {
      strict: true,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port,
    host: '0.0.0.0',
    allowedHosts: true,
  },
});
