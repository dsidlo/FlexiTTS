import { defineConfig } from 'vitest/config'
import viteConfig from './vite.config'

// https://vitest.dev/config/
export default defineConfig({
  ...viteConfig,
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/__tests__/setup.ts',
    include: ['src/__tests__/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}'],
    
    // Reporters:
    // - 'verbose' - Terminal output
    // - './scripts/dark-theme-reporter.ts' - Custom dark-themed HTML report
    // - 'json' - JSON report (when VITE_REPORT=true, for dashboard compatibility)
    reporter: process.env.VITE_REPORT === 'true' 
      ? ['verbose', './scripts/dark-theme-reporter.ts', 'json'] 
      : ['verbose', './scripts/dark-theme-reporter.ts'],
    
    outputFile: process.env.VITE_REPORT === 'true' 
      ? { json: './test-reports/test-results.json' }
      : undefined,
    
    // Coverage optional - use VITE_COVERAGE=true to enable
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: './test-reports/coverage',
      enabled: process.env.VITE_COVERAGE === 'true',
      all: false,
      include: ['src/**/*.ts', 'src/**/*.tsx'],
      exclude: [
        // Test files
        'src/__tests__/**',
        // Type definitions only
        'src/models/**',
        // Config files
        '**/*.config.*',
        '**/*.d.ts',
      ],
    },
  },
})
