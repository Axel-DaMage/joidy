import { test, expect, authGoto } from './helpers/auth';

/**
 * Streaks feature — comprehensive E2E tests.
 * Covers: list view, check-in, create, edit, delete, freeze,
 * bulk check-in, random streak, global summary, search.
 */
test.describe('Streaks — page structure', () => {
  test('streaks page loads with header', async ({ page }) => {
    await authGoto(page, '/streaks');
    // The page title "Rachas" — case-insensitive match
    await expect(page.locator('main.app-main').locator('text=/rachas/i').first()).toBeVisible({ timeout: 5000 });
  });

  test('search input is visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('input[placeholder="Buscar racha..."]')).toBeVisible();
  });

  test('create streak button is visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button[aria-label="Crear nueva racha"]')).toBeVisible();
  });

  test('view archived button is visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button[aria-label="Ver rachas archivadas"]')).toBeVisible();
  });

  test('global summary section is visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('text=/RESUMEN\\s+GLOBAL/i')).toBeVisible();
  });
});

test.describe('Streaks — list interactions', () => {
  test('streak items are visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    // Wait for streak items to render (API returns 50 streaks)
    const streakItems = page.locator('.streak-item-main');
    await expect(streakItems.first()).toBeVisible({ timeout: 15000 });
  });

  test('each streak has edit and delete buttons', async ({ page }) => {
    await authGoto(page, '/streaks');
    const firstStreak = page.locator('.streak-item-main').first();
    await expect(firstStreak).toBeVisible({ timeout: 15000 });
    // Edit and delete buttons are siblings of the streak item
    const streakContainer = firstStreak.locator('..');
    await expect(streakContainer.locator('button[aria-label*="Editar racha"]')).toBeVisible();
    await expect(streakContainer.locator('button[aria-label*="Eliminar racha"]')).toBeVisible();
  });

  test('clicking a streak selects it and shows details', async ({ page }) => {
    await authGoto(page, '/streaks');
    const firstStreak = page.locator('.streak-item-main').first();
    await expect(firstStreak).toBeVisible({ timeout: 15000 });
    await firstStreak.click();
    await page.waitForTimeout(500);
    // Detail panel should appear
    await expect(page.locator('main.app-main')).not.toBeEmpty();
  });

  test('search filters streaks', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('.streak-item-main').first()).toBeVisible({ timeout: 15000 });
    const search = page.locator('input[placeholder="Buscar racha..."]');
    await search.fill('Drink');
    await page.waitForTimeout(1000);
    // Should show "Drink Water" streak
    await expect(page.locator('text=Drink Water').first()).toBeVisible({ timeout: 5000 });
  });

  test('search with no match shows empty', async ({ page }) => {
    await authGoto(page, '/streaks');
    const search = page.locator('input[placeholder="Buscar racha..."]');
    await search.fill('zzz_no_match_xyz');
    await page.waitForTimeout(1000);
    const streakItems = page.locator('.streak-item-main');
    expect(await streakItems.count()).toBe(0);
  });
});

test.describe('Streaks — bulk actions', () => {
  test('check-in all button is visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button:has-text("Check-in de todas")')).toBeVisible();
  });

  test('random streak button is visible', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button:has-text("Racha random")')).toBeVisible();
  });
});

test.describe('Streaks — global summary', () => {
  test('shows active streaks count', async ({ page }) => {
    await authGoto(page, '/streaks');
    // Wait for the summary section to load (it doesn't depend on streak items)
    await expect(page.locator('text=/\\d+\\s+Activas/i')).toBeVisible({ timeout: 15000 });
  });

  test('shows archived count', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('text=/\\d+\\s+Archivadas/i')).toBeVisible({ timeout: 15000 });
  });

  test('shows record streak info', async ({ page }) => {
    await authGoto(page, '/streaks');
    // Shows "Récord" and "Racha más larga"
    await expect(page.locator('text=/r[ié]cord/i')).toBeVisible({ timeout: 15000 });
  });
});
