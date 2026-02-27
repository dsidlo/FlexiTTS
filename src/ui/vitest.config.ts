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
    
    // Test result reporters (pass/fail results)
    // Default: 'verbose' for detailed output
    // Optional: 'html' (requires @vitest/ui), 'json', 'junit'
    reporter: process.env.VITE_REPORT === 'true' 
      ? ['verbose', 'json'] 
      : ['verbose'],
    outputFile: process.env.VITE_REPORT === 'true' 
      ? './test-reports/test-results.json'
      : undefined,
    
    // Coverage optional - use VITE_COVERAGE=true to enable
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: './test-reports/coverage',
      enabled: process.env.VITE_COVERAGE === 'true',
    },
  },
})
