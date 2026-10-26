import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./vitest.setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/__tests__/**',
        'src/test/**',
        // The root layout only wires fonts, metadata and providers, which Next renders.
        'src/app/layout.tsx',
      ],
      reporter: ['text-summary', 'lcov'],
      // Floors sit a few points under current coverage, so they stop regressions.
      thresholds: { lines: 85, statements: 85, functions: 80, branches: 80 },
    },
  },
});
