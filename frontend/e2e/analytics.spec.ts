import { test, expect, authGoto } from './helpers/auth';

/**
 * Analytics page (#1499) — dedicated route, one-page layout (no scrolling),
 * labeled tabs, window selector and keyboard navigation.
 */
test.describe('Analytics — dedicated page', () => {
  test('is reachable from the sidebar without Dev Mode gating', async ({ page }) => {
    await authGoto(page, '/');
    await page.locator('nav.app-sidebar a[href="/analytics"]').click();
    await expect(page).toHaveURL(/\/analytics$/);
    await expect(page.locator('.header-tab').first()).toBeVisible({ timeout: 10000 });
  });

  test('renders every slide without any scroll container', async ({ page }) => {
    await authGoto(page, '/analytics');
    const tabs = page.locator('[role="tab"].header-tab');
    await expect(tabs.first()).toBeVisible({ timeout: 10000 });
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(5);
    for (let i = 0; i < count; i++) {
      await tabs.nth(i).click();
      // Wait for the slide switch to settle before measuring overflow.
      await expect(tabs.nth(i)).toHaveAttribute('aria-selected', 'true');
      const overflow = await page.evaluate(() => {
        const bad: string[] = [];
        document.querySelectorAll('.ad-root *').forEach((el) => {
          const s = getComputedStyle(el);
          if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && el.scrollHeight > el.clientHeight + 1)
            bad.push(el.className.toString());
        });
        return { bad, doc: document.documentElement.scrollHeight - innerHeight };
      });
      expect(overflow.bad).toEqual([]);
      expect(overflow.doc).toBeLessThanOrEqual(0);
    }
  });

  test('arrow keys move between slides and tabs expose ARIA state', async ({ page }) => {
    await authGoto(page, '/analytics');
    const tabs = page.locator('[role="tab"].header-tab');
    await expect(tabs.first()).toBeVisible({ timeout: 10000 });
    await tabs.first().click();
    await expect(tabs.first()).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('ArrowRight');
    await expect(tabs.nth(1)).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('[role="tabpanel"]')).toBeVisible();
  });

  test('window selector re-windows the dashboard', async ({ page }) => {
    await authGoto(page, '/analytics');
    const btn = page.locator('.header-segmented-btn').first();
    await expect(btn).toBeVisible({ timeout: 10000 });
    await btn.click();
    await expect(btn).toHaveClass(/active/);
  });
});
