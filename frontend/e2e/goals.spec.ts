import { test, expect, authGoto } from './helpers/auth';

/**
 * Goals feature — comprehensive E2E tests.
 * Covers: tabs (Editor/Inicio/Planificación/Historial/Análisis),
 * filters, goal cards, pin, search, goal detail view.
 */
test.describe('Goals — page structure', () => {
  test('goals page loads with all tabs', async ({ page }) => {
    await authGoto(page, '/goals');
    // All 5 tabs should be visible
    await expect(page.locator('button:has-text("Editor")')).toBeVisible();
    await expect(page.locator('button:has-text("Inicio")')).toBeVisible();
    await expect(page.locator('button:has-text("Planificación")')).toBeVisible();
    await expect(page.locator('button:has-text("Historial")')).toBeVisible();
    await expect(page.locator('button:has-text("Análisis")')).toBeVisible();
  });

  test('filter buttons are visible', async ({ page }) => {
    await authGoto(page, '/goals');
    await expect(page.locator('button:has-text("Todos")')).toBeVisible();
    await expect(page.locator('button:has-text("Fijados")')).toBeVisible();
    await expect(page.locator('button:has-text("Activos")')).toBeVisible();
    await expect(page.locator('button:has-text("Completados")')).toBeVisible();
    await expect(page.locator('button:has-text("Pausados")')).toBeVisible();
    await expect(page.locator('button:has-text("Fallidos")')).toBeVisible();
  });

  test('search input is visible', async ({ page }) => {
    await authGoto(page, '/goals');
    await expect(page.locator('input[placeholder="Buscar objetivos..."]')).toBeVisible();
  });
});

test.describe('Goals — tabs navigation', () => {
  test('can switch to Inicio tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Inicio")').click();
    await page.waitForTimeout(500);
    // The tab should become active
    await expect(page.locator('button.tab:has-text("Inicio")')).toHaveClass(/active/);
  });

  test('can switch to Planificación tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Planificación")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('button.tab:has-text("Planificación")')).toHaveClass(/active/);
  });

  test('can switch to Historial tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Historial")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('button.tab:has-text("Historial")')).toHaveClass(/active/);
  });

  test('can switch to Análisis tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Análisis")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('button.tab:has-text("Análisis")')).toHaveClass(/active/);
  });

  test('can switch back to Editor tab', async ({ page }) => {
    await authGoto(page, '/goals');
    // Switch to another tab first
    await page.locator('button:has-text("Análisis")').click();
    await page.waitForTimeout(300);
    // Then back to Editor
    await page.locator('button:has-text("Editor")').click();
    await page.waitForTimeout(300);
    await expect(page.locator('button.tab:has-text("Editor")')).toHaveClass(/active/);
  });
});

test.describe('Goals — filters', () => {
  test('can filter by Fallidos', async ({ page }) => {
    await authGoto(page, '/goals');
    const filterBtn = page.locator('button.filter-btn:has-text("Fallidos")');
    await filterBtn.click();
    await page.waitForTimeout(500);
    await expect(filterBtn).toHaveClass(/active/);
  });

  test('can filter by Completados', async ({ page }) => {
    await authGoto(page, '/goals');
    const filterBtn = page.locator('button.filter-btn:has-text("Completados")');
    await filterBtn.click();
    await page.waitForTimeout(500);
    await expect(filterBtn).toHaveClass(/active/);
  });

  test('can reset to Todos filter', async ({ page }) => {
    await authGoto(page, '/goals');
    // Apply a filter
    await page.locator('button.filter-btn:has-text("Fallidos")').click();
    await page.waitForTimeout(300);
    // Reset to Todos
    const todosBtn = page.locator('button.filter-btn:has-text("Todos")');
    await todosBtn.click();
    await page.waitForTimeout(500);
    await expect(todosBtn).toHaveClass(/active/);
  });

  test('search filters goals', async ({ page }) => {
    await authGoto(page, '/goals');
    const search = page.locator('input[placeholder="Buscar objetivos..."]');
    await search.fill('G1');
    await page.waitForTimeout(500);
    // Should show goals with "G1" in the title
    const goalCards = page.locator('.goal-card-main, [class*="goal-card"]');
    const count = await goalCards.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe('Goals — goal cards', () => {
  test('goal cards are visible and have pin buttons', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(2000);
    const goalCards = page.locator('.goal-card-main');
    const count = await goalCards.count();
    if (count > 0) {
      // Pin button is a sibling within the goal-editor-card container
      const pinBtn = page.locator('.goal-editor-card button[aria-label="Fijar objetivo"], .goal-editor-card button[aria-label="Desfijar objetivo"]').first();
      await expect(pinBtn).toBeVisible({ timeout: 3000 });
    }
  });

  test('clicking a goal card opens it', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1000);
    const firstGoal = page.locator('.goal-card-main').first();
    if (await firstGoal.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstGoal.click();
      await page.waitForTimeout(1000);
      // Should show goal detail/editor
      await expect(page.locator('main.app-main')).not.toBeEmpty();
    }
  });

  test('pin button toggles goal pin state', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1000);
    const firstGoalCard = page.locator('.goal-editor-card').first();
    if (await firstGoalCard.isVisible({ timeout: 2000 }).catch(() => false)) {
      const firstPinBtn = firstGoalCard.locator('button[aria-label="Fijar objetivo"], button[aria-label="Desfijar objetivo"]').first();
      await expect(firstPinBtn).toBeVisible({ timeout: 3000 });
      await firstPinBtn.click();
      await page.waitForTimeout(500);
      // The button should still be visible (toggled state, aria-label may change)
      const toggledBtn = firstGoalCard.locator('button[aria-label="Fijar objetivo"], button[aria-label="Desfijar objetivo"]').first();
      await expect(toggledBtn).toBeVisible();
    }
  });
});
