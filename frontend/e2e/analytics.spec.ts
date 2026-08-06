import { test, expect, authGoto } from './helpers/auth';

/**
 * Analytics feature — comprehensive E2E tests.
 * Covers: range tabs, system overview, charts, session stats, top pages.
 * Locale: Spanish (es) — set in auth helper.
 */
test.describe('Analytics — page structure', () => {
  test('analytics page loads with title', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Analytics page shows "ANALÍTICA" heading (Spanish locale)
    await expect(page.locator('main.app-main').locator('text=/analítica/i').first()).toBeVisible({ timeout: 5000 });
  });

  test('range tabs are visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Últimos 7d", "Últimos 30d", "Últimos 90d"
    await expect(page.locator('button.range-tab:has-text("Últimos 7d")')).toBeVisible();
    await expect(page.locator('button.range-tab:has-text("Últimos 30d")')).toBeVisible();
    await expect(page.locator('button.range-tab:has-text("Últimos 90d")')).toBeVisible();
  });
});

test.describe('Analytics — range tabs', () => {
  const ranges = ['Últimos 7d', 'Últimos 30d', 'Últimos 90d'];

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
    // Spanish: "Resumen del sistema"
    await expect(page.locator('text=/resumen del sistema/i')).toBeVisible({ timeout: 5000 });
  });

  test('notes count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Notas"
    await expect(page.locator('text=/\\d+\\s+Notas/i')).toBeVisible({ timeout: 5000 });
  });

  test('tags count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Etiquetas"
    await expect(page.locator('text=/\\d+\\s+Etiquetas/i')).toBeVisible({ timeout: 5000 });
  });

  test('goals count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Objetivos"
    await expect(page.locator('text=/\\d+\\s+Objetivos/i')).toBeVisible({ timeout: 5000 });
  });

  test('total XP is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "XP total"
    await expect(page.locator('text=/\\d+\\s+XP total/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Analytics — session stats', () => {
  test('session stats section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Estadísticas de sesión"
    await expect(page.locator('text=/estadísticas de sesión/i')).toBeVisible({ timeout: 5000 });
  });

  test('sessions count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Sesiones"
    await expect(page.locator('text=/\\d+\\s+Sesiones/i')).toBeVisible({ timeout: 5000 });
  });

  test('active days count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Días activos"
    await expect(page.locator('text=/\\d+\\s+Días activos/i')).toBeVisible({ timeout: 5000 });
  });

  test('total events count is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Eventos totales"
    await expect(page.locator('text=/\\d+\\s+Eventos totales/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Analytics — top pages', () => {
  test('top pages section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Páginas más visitadas"
    await expect(page.locator('text=/páginas más visitadas/i')).toBeVisible({ timeout: 5000 });
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
    // Spanish: "Tendencias de ánimo"
    await expect(page.locator('text=/tendencias de ánimo/i')).toBeVisible({ timeout: 5000 });
  });

  test('average mood is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Ánimo medio"
    await expect(page.locator('text=/ánimo medio/i')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Analytics — AI usage', () => {
  test('AI usage section is visible', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Uso de IA"
    await expect(page.locator('text=/uso de ia/i')).toBeVisible({ timeout: 5000 });
  });

  test('estimated cost is displayed', async ({ page }) => {
    await authGoto(page, '/analytics');
    // Spanish: "Coste estimado"
    await expect(page.locator('text=/coste estimado/i')).toBeVisible({ timeout: 5000 });
  });
});
