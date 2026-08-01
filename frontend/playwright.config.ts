import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E configuration for Joidy frontend.
 *
 * Tests run against the frontend dev server (Vite on port 3000). The API
 * must be reachable at VITE_API_URL (default http://localhost:8000) for
 * flows that exercise backend interactions.
 *
 * Usage:
 *   npx playwright test          # run all E2E
 *   npx playwright test --ui     # interactive mode
 *
 * In CI, the full Docker stack should be running before executing these
 * tests (see the `docker-build` job in .github/workflows/ci.yml).
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'html',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run dev',
        url: 'http://localhost:3000',
        reuseExistingServer: true,
        timeout: 60_000,
      },
});
