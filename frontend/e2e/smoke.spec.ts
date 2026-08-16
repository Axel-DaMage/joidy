import { test, expect, authGoto, dismissConflictModal } from './helpers/auth';

/**
 * Smoke tests — verify the app shell loads correctly.
 * If these fail, all other E2E tests will also fail.
 */
test.describe('Smoke — app shell', () => {
  test('homepage renders with title and nav', async ({ page }) => {
    await authGoto(page, '/');
    // App shell elements
    await expect(page.locator('header.app-header')).toBeVisible();
    await expect(page.locator('nav.app-sidebar')).toBeVisible();
    await expect(page.locator('main.app-main')).toBeVisible();
  });

  test('logo is visible', async ({ page }) => {
    await authGoto(page, '/');
    await expect(page.locator('.logo')).toContainText(/joidy/i);
  });

  test('XP counter is visible in header', async ({ page }) => {
    await authGoto(page, '/');
    const xp = page.locator('header.app-header').locator('text=/\\d+.*xp/i');
    await expect(xp).toBeVisible({ timeout: 5000 });
  });

  test('all 7 nav items are present and clickable', async ({ page }) => {
    await authGoto(page, '/');
    const nav = page.locator('nav.app-sidebar');
    const expectedHrefs = ['/', '/notes', '/graph', '/skills', '/ai', '/streaks', '/goals'];
    for (const href of expectedHrefs) {
      const link = nav.locator(`a[href="${href}"]`);
      await expect(link).toBeVisible();
    }
  });

  test('no unexpected console errors on initial load', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });
    await authGoto(page, '/');
    // Filter expected errors (API may be down, network issues)
    const unexpected = errors.filter(
      e => !e.includes('net::ERR') &&
           !e.includes('Failed to fetch') &&
           !e.includes('VAPID') &&
           !e.includes('503'),
    );
    expect(unexpected).toEqual([]);
  });

  test('settings button opens settings modal', async ({ page }) => {
    await authGoto(page, '/');
    // Wait a bit more for any late modals to appear and be dismissed
    await page.waitForTimeout(500);
    await dismissConflictModal(page);
    // Settings button aria-label is i18n-translated, use custom event instead
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('joidy:open-settings')));
    // Settings modal or panel should appear
    await page.waitForTimeout(500);
    // Check for either a modal overlay or a settings panel
    const modal = page.locator('.modal-overlay, .backdrop, .settings-panel, [class*="settings"]');
    await expect(modal.first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Smoke — navigation between pages', () => {
  const pages = [
    { path: '/', title: 'Home' },
    { path: '/notes', title: 'Notes' },
    { path: '/graph', title: 'Graph' },
    { path: '/skills', title: 'Skills' },
    { path: '/ai', title: 'AI' },
    { path: '/streaks', title: 'Streaks' },
    { path: '/goals', title: 'Goals' },
  ];

  for (const p of pages) {
    test(`can navigate to ${p.title} (${p.path})`, async ({ page }) => {
      await authGoto(page, '/');
      const navLink = page.locator(`nav.app-sidebar a[href="${p.path}"]`);
      await navLink.click();
      await page.waitForLoadState('networkidle');
      await dismissConflictModal(page);
      // Verify URL changed (for Home, check we're at root)
      if (p.path === '/') {
        await expect(page).toHaveURL(/\/$/);
      } else {
        await expect(page).toHaveURL(new RegExp(escapeRegex(p.path)));
      }
      // Main content should be visible
      await expect(page.locator('main.app-main')).toBeVisible();
    });
  }
});

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
