import { test, expect } from '@playwright/test';

/**
 * Smoke test: verifies the frontend loads and shows the main dashboard.
 * This is the baseline E2E test — if it fails, all other E2E tests will
 * also fail.
 */
test.describe('Smoke — app loads', () => {
  test('homepage renders the dashboard', async ({ page }) => {
    await page.goto('/');
    // The app should show some content (not a blank page or error)
    await expect(page).toHaveTitle(/joidy/i);
    // Wait for the main content to appear
    await page.waitForLoadState('networkidle');
    const body = page.locator('body');
    await expect(body).not.toBeEmpty();
  });

  test('no console errors on initial load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    // Filter out expected network errors (API may be down in some test envs)
    const unexpected = errors.filter(
      e => !e.includes('net::ERR') && !e.includes('Failed to fetch'),
    );
    expect(unexpected).toEqual([]);
  });
});
