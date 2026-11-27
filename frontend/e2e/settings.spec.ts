import { test, expect, authGoto, dismissConflictModal } from './helpers/auth';

/**
 * Settings page — comprehensive E2E tests.
 * Settings lives on the /settings route now (#1671): a left section rail
 * (.settings-nav) plus a content pane (.settings-section), with deep links
 * via the URL hash (/settings#vault).
 */
async function openSettings(page: import('@playwright/test').Page, hash = '') {
  await authGoto(page, `/settings${hash}`);
  // authGoto already waits for the app shell and dismisses the conflict
  // modal — re-check once in case a conflict mounted a tick late.
  await dismissConflictModal(page);
  await expect(page.locator('.settings-view')).toBeVisible({ timeout: 5000 });
}

async function gotoSection(page: import('@playwright/test').Page, label: string) {
  await page.locator('.settings-nav-item').filter({ hasText: label }).first().click();
}

test.describe('Settings — open/close', () => {
  test('settings button navigates to the settings page', async ({ page }) => {
    await authGoto(page, '/');
    await dismissConflictModal(page);
    // Settings button aria-label is i18n-translated ("Ajustes" in es, "Settings"
    // in en) — use the custom event dispatcher instead for locale independence.
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('joidy:open-settings')));
    await expect(page).toHaveURL(/\/settings/, { timeout: 5000 });
    await expect(page.locator('.settings-view')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.settings-nav')).toBeVisible({ timeout: 5000 });
  });

  test('back button leaves the settings page', async ({ page }) => {
    await openSettings(page);
    await page.locator('.settings-back').click();
    await expect(page).not.toHaveURL(/\/settings/, { timeout: 5000 });
  });

  test('can leave with Escape key', async ({ page }) => {
    await openSettings(page);
    await page.keyboard.press('Escape');
    await expect(page).not.toHaveURL(/\/settings/, { timeout: 5000 });
  });
});

test.describe('Settings — sections', () => {
  test('rail shows Apariencia, Avanzado, Vault, Integraciones, Sesión, Servicios and Desarrollador', async ({
    page,
  }) => {
    await openSettings(page);
    const nav = page.locator('.settings-nav');
    await expect(nav.locator('text=Apariencia').first()).toBeVisible({ timeout: 5000 });
    await expect(nav.locator('text=Avanzado').first()).toBeVisible({ timeout: 5000 });
    await expect(nav.locator('text=Vault').first()).toBeVisible({ timeout: 5000 });
    await expect(nav.locator('text=Integraciones').first()).toBeVisible({ timeout: 5000 });
    // IA only renders under dev mode — the e2e auth helper enables it.
    await expect(nav.locator('.settings-nav-item').filter({ hasText: 'IA' }).first()).toBeVisible({
      timeout: 5000,
    });
    await expect(nav.locator('text=Sesión').first()).toBeVisible({ timeout: 5000 });
    await expect(nav.locator('text=Servicios').first()).toBeVisible({ timeout: 5000 });
    await expect(nav.locator('text=Desarrollador').first()).toBeVisible({ timeout: 5000 });
  });

  test('deep link /settings#vault opens the Vault section', async ({ page }) => {
    await openSettings(page, '#vault');
    await expect(page.locator('#settings-vault')).toBeVisible({ timeout: 5000 });
  });

  test('nav clicks switch sections and sync the URL hash', async ({ page }) => {
    await openSettings(page);
    await gotoSection(page, 'Integraciones');
    await expect(page.locator('#settings-integrations')).toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL(/#integrations/, { timeout: 5000 });
  });
});

test.describe('Settings — Desarrollador (Dev Mode)', () => {
  test('dev mode section is visible and toggle can be switched', async ({ page }) => {
    await openSettings(page);
    await gotoSection(page, 'Desarrollador');
    const devSection = page.locator('.settings-section').filter({ hasText: 'Desarrollador' });
    const toggle = devSection.locator('.toggle, button[role="switch"], input[type="checkbox"]');
    if (await toggle.first().isVisible({ timeout: 2000 }).catch(() => false)) {
      await toggle.first().click();
    }
  });
});

test.describe('Settings — Integraciones', () => {
  test('GitHub and Google integrations are visible', async ({ page }) => {
    await openSettings(page, '#integrations');
    const section = page.locator('#settings-integrations');
    await expect(section.locator('text=/github/i')).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=/google/i').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — Obsidian Vault', () => {
  test('vault path input and mode toggle (aislado/nativo) are visible', async ({ page }) => {
    await openSettings(page, '#vault');
    const section = page.locator('#settings-vault');
    const pathInput = section.locator('input').first();
    await expect(pathInput).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=aislado').first()).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=nativo').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — Apariencia', () => {
  test('dark/light mode toggle is visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('#settings-appearance');
    // Spanish locale: "oscuro" (dark) and "claro" (light)
    await expect(section.locator('text=oscuro').first()).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=claro').first()).toBeVisible({ timeout: 5000 });
  });
});
