import { test, expect, authGoto } from './helpers/auth';

/**
 * Skills feature — comprehensive E2E tests.
 * Covers: tree view, level filters, skill list.
 */
test.describe('Skills — page structure', () => {
  test('skills page renders title, banner, count and level filter buttons', async ({
    page,
  }) => {
    await authGoto(page, '/skills');
    await expect(page.locator('text=/árbol de habilidades/i')).toBeVisible();
    await expect(page.locator('.beta-banner')).toBeVisible();
    // "0 habilidades desbloqueadas" — use .first() to avoid strict mode violation
    await expect(page.locator('text=/\\d+\\s+habilidades/i').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button.level-filter-btn:has-text("Todas")')).toBeVisible();
    await expect(page.locator('button.level-filter-btn:has-text("Bloqueado")')).toBeVisible();
    await expect(page.locator('button.level-filter-btn:has-text("Aprendiz")')).toBeVisible();
    await expect(page.locator('button.level-filter-btn:has-text("Oficial")')).toBeVisible();
    await expect(page.locator('button.level-filter-btn:has-text("Experto")')).toBeVisible();
    await expect(page.locator('button.level-filter-btn:has-text("Maestro")')).toBeVisible();
  });
});

test.describe('Skills — level filters', () => {
  test('can filter by each level', async ({ page }) => {
    await authGoto(page, '/skills');
    const levels = ['Bloqueado', 'Aprendiz', 'Oficial', 'Experto', 'Maestro'];
    for (const level of levels) {
      const btn = page.locator(`button.level-filter-btn:has-text("${level}")`);
      await btn.click();
      await expect(btn).toHaveClass(/active/);
    }
  });

  test('can reset to Todas', async ({ page }) => {
    await authGoto(page, '/skills');
    // Apply a filter
    await page.locator('button.level-filter-btn:has-text("Aprendiz")').click();
    // Reset
    const todasBtn = page.locator('button.level-filter-btn:has-text("Todas")');
    await todasBtn.click();
    await expect(todasBtn).toHaveClass(/active/);
  });
});

test.describe('Skills — skill tree', () => {
  test('skill tree or empty state is displayed with level progression labels', async ({
    page,
  }) => {
    await authGoto(page, '/skills');
    // Either skills are shown or an empty state message
    const main = page.locator('main.app-main');
    await expect(main).not.toBeEmpty();
    // The progression labels: Aprendiz, Oficial, Experto, Maestro
    await expect(page.locator('text=Aprendiz').first()).toBeVisible();
    await expect(page.locator('text=Oficial').first()).toBeVisible();
    await expect(page.locator('text=Experto').first()).toBeVisible();
    await expect(page.locator('text=Maestro').first()).toBeVisible();
  });
});
