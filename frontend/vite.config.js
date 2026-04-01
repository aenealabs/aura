/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      exclude: ['node_modules/', 'src/test/'],
    },
  },
  server: {
    port: 3000,
    // Proxy API requests to the backend during development
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // Target modern browsers for smaller bundles
    target: 'es2020',
    // Use esbuild for fast minification (default, explicit for clarity)
    minify: 'esbuild',
    // Increase chunk size warning threshold for vendor chunks
    chunkSizeWarningLimit: 600,
    // CSS code splitting for lazy-loaded routes
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        // Function-based manual chunks for precise control
        manualChunks: (id) => {
          // React core - loaded on every page
          if (
            id.includes('node_modules/react/') ||
            id.includes('node_modules/react-dom/') ||
            id.includes('node_modules/react-router-dom/') ||
            id.includes('node_modules/scheduler/')
          ) {
            return 'vendor-react';
          }

          // UI icons - commonly used across pages
          if (
            id.includes('node_modules/@heroicons/') ||
            id.includes('node_modules/lucide-react/')
          ) {
            return 'vendor-icons';
          }

          // Mermaid + all its dependencies - only load when needed
          if (
            id.includes('node_modules/mermaid/') ||
            id.includes('node_modules/cytoscape/') ||
            id.includes('node_modules/d3') ||
            id.includes('node_modules/katex/') ||
            id.includes('node_modules/dagre-d3') ||
            id.includes('node_modules/dagre/') ||
            id.includes('node_modules/khroma/') ||
            id.includes('node_modules/dompurify/') ||
            id.includes('node_modules/roughjs/') ||
            id.includes('node_modules/lodash-es/') ||
            id.includes('node_modules/marked/')
          ) {
            return 'vendor-mermaid';
          }

          // Cognito auth - only needed during auth flow
          if (id.includes('node_modules/amazon-cognito-identity-js/')) {
            return 'vendor-auth';
          }

          // React Grid Layout - only used on Dashboard
          if (
            id.includes('node_modules/react-grid-layout/') ||
            id.includes('node_modules/react-draggable/') ||
            id.includes('node_modules/react-resizable/')
          ) {
            return 'vendor-grid';
          }
        },
      },
    },
  },
  // Environment variable prefix for client-side code
  envPrefix: 'VITE_',
});
