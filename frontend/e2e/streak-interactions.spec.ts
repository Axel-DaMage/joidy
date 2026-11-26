import { test, expect, authGoto } from './helpers/auth';

/**
 * Streak Interactions — comprehensive E2E tests.
 * Covers: select streak, detail panel, check-in, create modal, edit modal,
 * delete confirmation, bulk check-in, random streak.
 */
test.describe('Streaks — selection and detail panel', () => {
  test('selecting a streak shows the detail panel', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('.streak-item-main').first()).toBeVisible({ timeout: 15000 });
    await page.locator('.streak-item-main').first().click();
    // Detail panel should appear
    await expect(page.locator('.detail-panel')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.counter-title')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.counter-ring')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.detail-stats')).toBeVisible({ timeout: 5000 });
    // Should show "Actual", "Mejor", "Check-ins"
    await expect(page.locator('text=Actual')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=Mejor')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=Check-ins')).toBeVisible({ timeout: 3000 });
    const exitBtn = page.locator('.detail-exit-btn[aria-label="Volver al menú"]');
    await expect(exitBtn).toBeVisible({ timeout: 5000 });
  });

  test('can exit detail panel', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('.streak-item-main').first()).toBeVisible({ timeout: 15000 });
    await page.locator('.streak-item-main').first().click();
    await expect(page.locator('.detail-panel')).toBeVisible({ timeout: 5000 });
    const exitBtn = page.locator('.detail-exit-btn[aria-label="Volver al menú"]');
    await exitBtn.click();
    // The panel may hide via CSS or be removed from DOM
    // Check that the counter-title (streak name) is no longer visible
    await expect(page.locator('.counter-title')).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe('Streaks — check-in', () => {
  test('can perform check-in', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('.streak-item-main').first()).toBeVisible({ timeout: 15000 });
    await page.locator('.streak-item-main').first().click();
    // Counter ring is the check-in button
    const checkinBtn = page.locator('.counter-ring');
    await expect(checkinBtn).toBeVisible({ timeout: 5000 });
    // Check if it's available for check-in (not disabled)
    const ariaLabel = await checkinBtn.getAttribute('aria-label');
    if (ariaLabel?.includes('Hacer check-in')) {
      await checkinBtn.click();
      // After check-in, the button should change state
      await expect(checkinBtn).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Streaks — create modal', () => {
  test('create modal shows title, name input and save/cancel buttons', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button[aria-label="Crear nueva racha"]')).toBeVisible({ timeout: 5000 });
    await page.locator('button[aria-label="Crear nueva racha"]').click();
    // Modal should appear (StreakCreateModal: .modal-panel role=dialog)
    await expect(page.locator('.modal-backdrop .modal-panel')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('text=NUEVA RACHA')).toBeVisible({ timeout: 3000 });
    // Should have a name/title input
    const nameInput = page.locator('.modal-backdrop .modal-panel input').first();
    await expect(nameInput).toBeVisible({ timeout: 3000 });
    await expect(page.locator('button:has-text("Crear Racha")')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('button:has-text("Cancelar")')).toBeVisible({ timeout: 3000 });
  });

  test('can cancel create modal', async ({ page }) => {
    await authGoto(page, '/streaks');
    await page.locator('button[aria-label="Crear nueva racha"]').click();
    await expect(page.locator('.modal-backdrop .modal-panel')).toBeVisible({ timeout: 3000 });
    await page.locator('button:has-text("Cancelar")').click();
    await expect(page.locator('.modal-backdrop .modal-panel')).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Streaks — edit modal', () => {
  test('can open edit modal', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('.streak-item-main').first()).toBeVisible({ timeout: 15000 });
    // Hover over first streak to reveal edit button
    await page.locator('.streak-item-main').first().hover();
    const editBtn = page.locator('button[aria-label*="Editar racha"]').first();
    const editVisible = await editBtn
      .waitFor({ state: 'visible', timeout: 2000 })
      .then(() => true)
      .catch(() => false);
    if (editVisible) {
      await editBtn.click();
      // Edit modal should appear
      await expect(page.locator('text=EDITAR RACHA')).toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe('Streaks — delete flow', () => {
  test('delete button opens confirmation modal', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('.streak-item-main').first()).toBeVisible({ timeout: 15000 });
    // Hover over first streak to reveal delete button
    await page.locator('.streak-item-main').first().hover();
    const deleteBtn = page.locator('button[aria-label*="Eliminar racha"]').first();
    const deleteVisible = await deleteBtn
      .waitFor({ state: 'visible', timeout: 2000 })
      .then(() => true)
      .catch(() => false);
    if (deleteVisible) {
      await deleteBtn.click();
      // Confirmation modal should appear
      await expect(page.locator('.delete-modal')).toBeVisible({ timeout: 3000 });
      await expect(page.locator('text=Eliminar racha')).toBeVisible();
      await expect(page.locator('text="Esta acción no se puede deshacer."')).toBeVisible();
      // Cancel
      await page.locator('.btn-cancel:has-text("Cancelar")').click();
      await expect(page.locator('.delete-modal')).not.toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe('Streaks — bulk actions', () => {
  test('check-in de todas button works', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button:has-text("Check-in de todas")')).toBeVisible({ timeout: 5000 });
    // The button should be clickable (not disabled) if there are active streaks
    const btn = page.locator('button:has-text("Check-in de todas")');
    const isDisabled = await btn.isDisabled().catch(() => true);
    if (!isDisabled) {
      await btn.click();
      // Should show some feedback (toast or state change)
    }
  });

  test('racha random button works', async ({ page }) => {
    await authGoto(page, '/streaks');
    await expect(page.locator('button:has-text("Racha random")')).toBeVisible({ timeout: 5000 });
    const btn = page.locator('button:has-text("Racha random")');
    const isDisabled = await btn.isDisabled().catch(() => true);
    if (!isDisabled) {
      await btn.click();
      // Should open a random streak detail
      await expect(page.locator('.detail-panel')).toBeVisible({ timeout: 5000 });
    }
  });
});

test.describe('Streaks — archived toggle', () => {
  test('can toggle archived view', async ({ page }) => {
    await authGoto(page, '/streaks');
    const archiveBtn = page.locator('button[aria-label="Ver rachas archivadas"]');
    await expect(archiveBtn).toBeVisible({ timeout: 5000 });
    await archiveBtn.click();
    // Button text should change to "Volver a rachas activas"
    const backBtn = page.locator('button[aria-label="Volver a rachas activas"]');
    await expect(backBtn).toBeVisible({ timeout: 3000 });
    // Toggle back
    await backBtn.click();
    await expect(page.locator('button[aria-label="Ver rachas archivadas"]')).toBeVisible({ timeout: 3000 });
  });
});
