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
      include: ['src/lib/**', 'src/hooks/**', 'src/components/**'],
      reporter: ['text-summary', 'lcov'],
      // Floors sit just under current coverage, so they only stop regressions. Raise them as tests land.
      thresholds: { lines: 10, statements: 10, functions: 7, branches: 6 },
    },
  },
});
