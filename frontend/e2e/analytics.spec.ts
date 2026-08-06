import { test, expect, authGoto } from './helpers/auth';

/**
 * Analytics feature — comprehensive E2E tests.
 * Covers: range tabs, system overview, charts, session stats, top pages.
 */
test.describe('Analytics — page structure', () => {
  test('analytics page loads with title', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Analytics page shows "ANALYTICS" heading
    await expect(page.locator('main.app-main').locator('text=/analytics/i').first()).toBeVisible({ timeout: 5000 });
  });

  test('range tabs are visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('button.range-tab:has-text("Last 7d")')).toBeVisible();
    await expect(page.locator('button.range-tab:has-text("Last 30d")')).toBeVisible();
    await expect(page.locator('button.range-tab:has-text("Last 90d")')).toBeVisible();
  });
});

test.describe('Analytics — range tabs', () => {
  const ranges = ['Last 7d', 'Last 30d', 'Last 90d'];

  for (const range of ranges) {
    test(`can switch to ${range}`, async ({ page }) => {
      await authGoto(page, '/analytics');
      const btn = page.locator(`button.range-tab:has-text("${range}")`);
      await btn.click();
      await page.waitForTimeout(500);
      await expect(btn).toHaveClass(/active/);
    });
  }
});

test.describe('Analytics — system overview', () => {
  test('system overview section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/system overview/i')).toBeVisible({ timeout: 5000 });
  });

  test('notes count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Notes/i')).toBeVisible({ timeout: 5000 });
  });

  test('tags count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Tags/i')).toBeVisible({ timeout: 5000 });
  });

  test('goals count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Goals/i')).toBeVisible({ timeout: 5000 });
  });

  test('total XP is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Total XP/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Analytics — session stats', () => {
  test('session stats section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/session stats/i')).toBeVisible({ timeout: 5000 });
  });

  test('sessions count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Sessions/i')).toBeVisible({ timeout: 5000 });
  });

  test('active days count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Active days/i')).toBeVisible({ timeout: 5000 });
  });

  test('total events count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\d+\\s+Total events/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Analytics — top pages', () => {
  test('top pages section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/top pages/i')).toBeVisible({ timeout: 5000 });
  });

  test('top pages list has entries', async ({ page }) => {
    await authGoto(page, '/analytics');
    await page.waitForTimeout(1000);
    // Top pages should show page paths with counts like "/ 17"
    const topPages = page.locator('text=/\\/\\s+\\d+/');
    const count = await topPages.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('Analytics — mood trends', () => {
  test('mood trends section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/mood trends/i')).toBeVisible({ timeout: 5000 });
  });

  test('average mood is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/avg mood/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Analytics — AI usage', () => {
  test('AI usage section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/ai usage/i')).toBeVisible({ timeout: 5000 });
  });

  test('estimated cost is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    await expect(page.locator('text=/\\$[\\d.]+\\s+estimated cost/i')).toBeVisible({ timeout: 5000 });
  });
});
