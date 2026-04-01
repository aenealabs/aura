import { defineConfig } from 'tsup';

export default defineConfig([
  // Main entry point
  {
    entry: ['src/index.ts'],
    format: ['cjs', 'esm'],
    dts: true,
    sourcemap: true,
    clean: true,
    treeshake: true,
    splitting: false,
    outDir: 'dist',
  },
  // React entry point
  {
    entry: ['src/react.ts'],
    format: ['cjs', 'esm'],
    dts: true,
    sourcemap: true,
    treeshake: true,
    splitting: false,
    outDir: 'dist',
    external: ['react'],
  },
]);
