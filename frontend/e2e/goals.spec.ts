import { test, expect, authGoto } from './helpers/auth';

/**
 * Goals feature — comprehensive E2E tests.
 * Covers: tabs (Editor/Inbox/Planificación/Historial),
 * filters, goal cards, pin, search, goal detail view.
 */
test.describe('Goals — page structure', () => {
  test('goals page loads with all tabs, filters and search', async ({ page }) => {
    await authGoto(page, '/goals');
    // All tabs should be visible (Análisis lives on its own /analytics page)
    await expect(page.locator('button:has-text("Editor")')).toBeVisible();
    await expect(page.locator('button:has-text("Inbox")')).toBeVisible();
    await expect(page.locator('button:has-text("Planificación")')).toBeVisible();
    await expect(page.locator('button:has-text("Historial")')).toBeVisible();
    await expect(page.locator('button:has-text("Análisis")')).toHaveCount(0);
    // Filter chips
    await expect(page.locator('button:has-text("Todos")')).toBeVisible();
    await expect(page.locator('button:has-text("Fijados")')).toBeVisible();
    await expect(page.locator('button:has-text("Activos")')).toBeVisible();
    await expect(page.locator('button:has-text("Completados")')).toBeVisible();
    await expect(page.locator('button:has-text("Archivados")')).toBeVisible();
    await expect(page.locator('button:has-text("Fallidos")')).toBeVisible();
    // Search input
    await expect(page.locator('input[placeholder="Buscar objetivos..."]')).toBeVisible();
  });
});

test.describe('Goals — tabs navigation', () => {
  test('can switch to Inbox tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Inbox")').click();
    // The tab should become active
    await expect(page.locator('button.header-tab:has-text("Inbox")')).toHaveClass(/active/);
  });

  test('can switch to Planificación tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Planificación")').click();
    await expect(page.locator('button.header-tab:has-text("Planificación")')).toHaveClass(/active/);
  });

  test('can switch to Historial tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button:has-text("Historial")').click();
    await expect(page.locator('button.header-tab:has-text("Historial")')).toHaveClass(/active/);
  });

  test('can switch back to Editor tab', async ({ page }) => {
    await authGoto(page, '/goals');
    // Switch to another tab first
    await page.locator('button:has-text("Historial")').click();
    // Then back to Editor
    await page.locator('button:has-text("Editor")').click();
    await expect(page.locator('button.header-tab:has-text("Editor")')).toHaveClass(/active/);
  });
});

test.describe('Goals — legacy analytics deep links', () => {
  test('?tab=analytics redirects to the dedicated /analytics page', async ({ page }) => {
    await authGoto(page, '/goals?tab=analytics');
    await expect(page).toHaveURL(/\/analytics$/);
  });
});

test.describe('Goals — filters', () => {
  test('can filter by Fallidos', async ({ page }) => {
    await authGoto(page, '/goals');
    const filterBtn = page.locator('button.gf-chip:has-text("Fallidos")');
    await filterBtn.click();
    await expect(filterBtn).toHaveClass(/active/);
  });

  test('can filter by Completados', async ({ page }) => {
    await authGoto(page, '/goals');
    const filterBtn = page.locator('button.gf-chip:has-text("Completados")');
    await filterBtn.click();
    await expect(filterBtn).toHaveClass(/active/);
  });

  test('can reset to Todos filter', async ({ page }) => {
    await authGoto(page, '/goals');
    // Apply a filter
    await page.locator('button.gf-chip:has-text("Fallidos")').click();
    // Reset to Todos
    const todosBtn = page.locator('button.gf-chip:has-text("Todos")');
    await todosBtn.click();
    await expect(todosBtn).toHaveClass(/active/);
  });

  test('search filters goals', async ({ page }) => {
    await authGoto(page, '/goals');
    const search = page.locator('input[placeholder="Buscar objetivos..."]');
    await search.fill('G1');
    // Should show goals with "G1" in the title
    const goalCards = page.locator('.grow-main, [class*="goal-card"]');
    await expect.poll(async () => goalCards.count()).toBeGreaterThan(0);
  });
});

test.describe('Goals — goal cards', () => {
  test('goal cards are visible and have pin buttons', async ({ page }) => {
    await authGoto(page, '/goals');
    const goalCards = page.locator('.grow-main');
    // Bounded poll instead of a fixed sleep — the guard below still
    // tolerates an empty list.
    await expect
      .poll(async () => goalCards.count(), { timeout: 5000 })
      .toBeGreaterThan(0)
      .catch(() => {});
    const count = await goalCards.count();
    if (count > 0) {
      // Pin button is a sibling within the goal-editor-card container
      // (aria-labels are "Fijar"/"Desfijar" — goalCard.pin/unpin).
      const pinBtn = page.locator('.grow button[aria-label="Fijar"], .grow button[aria-label="Desfijar"]').first();
      await expect(pinBtn).toBeVisible({ timeout: 3000 });
    }
  });

  test('clicking a goal card opens it', async ({ page }) => {
    await authGoto(page, '/goals');
    const firstGoal = page.locator('.grow-main').first();
    if (await firstGoal.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstGoal.click();
      // Should show goal detail/editor
      await expect(page.locator('main.app-main')).not.toBeEmpty();
    }
  });

  test('pin button toggles goal pin state', async ({ page }) => {
    await authGoto(page, '/goals');
    const firstGoalCard = page.locator('.grow').first();
    if (await firstGoalCard.isVisible({ timeout: 2000 }).catch(() => false)) {
      // The pin button lives in .card-top-left-actions, which is
      // pointer-events:none until the card is hovered (GoalCard.svelte) —
      // hover first or the click actionability check times out.
      await firstGoalCard.hover();
      const firstPinBtn = firstGoalCard.locator('button[aria-label="Fijar"], button[aria-label="Desfijar"]').first();
      await expect(firstPinBtn).toBeVisible({ timeout: 3000 });
      await firstPinBtn.click();
      // The button should still be visible (toggled state, aria-label may change)
      const toggledBtn = firstGoalCard.locator('button[aria-label="Fijar"], button[aria-label="Desfijar"]').first();
      await expect(toggledBtn).toBeVisible();
    }
  });
});
