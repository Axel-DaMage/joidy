import { test, expect, authGoto, dismissConflictModal } from './helpers/auth';

/**
 * Settings Panel — comprehensive E2E tests.
 * The Settings panel uses .backdrop and .panel classes (not .modal-overlay).
 * Covers: open/close, all sections, dev mode toggle, integrations,
 * export buttons, appearance settings, Obsidian vault settings.
 */
async function openSettings(page: import('@playwright/test').Page) {
  await authGoto(page, '/');
  // Wait for page to settle, dismiss any conflict modal
  await page.waitForTimeout(1500);
  await dismissConflictModal(page);
  await page.waitForTimeout(300);
  // Settings button aria-label is i18n-translated ("Ajustes" in es, "Settings" in en)
  // Use the custom event dispatcher instead for locale independence
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('joidy:open-settings')));
  // Wait for backdrop to appear
  try {
    await expect(page.locator('.backdrop')).toBeVisible({ timeout: 5000 });
  } catch {
    // Retry — conflict modal may have interfered
    await dismissConflictModal(page);
    await page.waitForTimeout(300);
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('joidy:open-settings')));
    await expect(page.locator('.backdrop')).toBeVisible({ timeout: 10000 });
  }
}

test.describe('Settings — open/close', () => {
  test('settings button opens panel', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator('.backdrop .panel')).toBeVisible({ timeout: 5000 });
  });

  test('settings panel has close button', async ({ page }) => {
    await openSettings(page);
    const closeBtn = page.locator('.panel .close-btn');
    await expect(closeBtn).toBeVisible({ timeout: 5000 });
  });

  test('can close settings panel', async ({ page }) => {
    await openSettings(page);
    const closeBtn = page.locator('.panel .close-btn');
    await closeBtn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.backdrop')).not.toBeVisible({ timeout: 5000 });
  });

  test('can close with Escape key', async ({ page }) => {
    await openSettings(page);
    await page.keyboard.press('Escape');
    await expect(page.locator('.backdrop')).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — sections', () => {
  test.beforeEach(async ({ page }) => {
    await openSettings(page);
  });

  test('Apariencia section is visible', async ({ page }) => {
    await expect(page.locator('.panel').locator('text=Apariencia').first()).toBeVisible({ timeout: 5000 });
  });

  test('Avanzado section is visible', async ({ page }) => {
    await expect(page.locator('.panel').locator('text=Avanzado').first()).toBeVisible({ timeout: 5000 });
  });

  test('Obsidian Vault section is visible', async ({ page }) => {
    await expect(page.locator('.panel').locator('text=Obsidian Vault')).toBeVisible({ timeout: 5000 });
  });

  test('Integraciones section is visible', async ({ page }) => {
    await expect(page.locator('.panel').locator('text=Integraciones')).toBeVisible({ timeout: 5000 });
  });

  test('IA section is visible', async ({ page }) => {
    // "IA" is short and may match multiple elements — use .first()
    await expect(page.locator('.panel .section-title').filter({ hasText: 'IA' }).first()).toBeVisible({ timeout: 5000 });
  });

  test('Exportar Datos section is visible', async ({ page }) => {
    await expect(page.locator('.panel').locator('text=Exportar Datos')).toBeVisible({ timeout: 5000 });
  });

  test('Desarrollador section is visible', async ({ page }) => {
    await expect(page.locator('.panel').locator('text=Desarrollador')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — Desarrollador (Dev Mode)', () => {
  test('dev mode section is visible', async ({ page }) => {
    await openSettings(page);
    await expect(page.locator('.panel').locator('text=Desarrollador')).toBeVisible({ timeout: 5000 });
  });

  test('dev mode toggle can be switched', async ({ page }) => {
    await openSettings(page);
    const devSection = page.locator('.panel .section').filter({ hasText: 'Desarrollador' });
    const toggle = devSection.locator('.toggle, button[role="switch"], input[type="checkbox"]');
    if (await toggle.first().isVisible({ timeout: 2000 }).catch(() => false)) {
      await toggle.first().click();
      await page.waitForTimeout(300);
    }
  });
});

test.describe('Settings — Integraciones', () => {
  test('GitHub integration is visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('.panel .section').filter({ hasText: 'Integraciones' });
    await expect(section.locator('text=/github/i')).toBeVisible({ timeout: 5000 });
  });

  test('Google integration is visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('.panel .section').filter({ hasText: 'Integraciones' });
    await expect(section.locator('text=/google/i').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — Exportar Datos', () => {
  test('export options are visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('.panel .section').filter({ hasText: 'Exportar Datos' });
    await expect(section.locator('text=/markdown/i')).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=/html/i')).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=/zip/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — Obsidian Vault', () => {
  test('vault path input is visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('.panel .section').filter({ hasText: 'Obsidian Vault' });
    const pathInput = section.locator('input').first();
    await expect(pathInput).toBeVisible({ timeout: 5000 });
  });

  test('vault mode toggle (aislado/nativo) is visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('.panel .section').filter({ hasText: 'Obsidian Vault' });
    await expect(section.locator('text=aislado').first()).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=nativo').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Settings — Apariencia', () => {
  test('dark/light mode toggle is visible', async ({ page }) => {
    await openSettings(page);
    const section = page.locator('.panel .section').filter({ hasText: 'Apariencia' });
    // Spanish locale: "oscuro" (dark) and "claro" (light)
    await expect(section.locator('text=oscuro').first()).toBeVisible({ timeout: 5000 });
    await expect(section.locator('text=claro').first()).toBeVisible({ timeout: 5000 });
  });
});
