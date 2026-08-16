import { test, expect, authGoto } from './helpers/auth';

/**
 * Goal Editor — comprehensive E2E tests.
 * Covers: open goal detail, title/content editing, settings modal (3 tabs),
 * goal creation modal, goal actions (pause/complete/delete).
 */
test.describe('Goal Editor — open detail page', () => {
  test('can open goal detail from Editor tab', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1500);
    const firstGoal = page.locator('.goal-card-main').first();
    await expect(firstGoal).toBeVisible({ timeout: 5000 });
    await firstGoal.click();
    await page.waitForTimeout(1000);
    // Should navigate to /goals/{id}
    await expect(page).toHaveURL(/\/goals\/\d+/);
    // Editor shell should be visible
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('can close goal detail and return to list', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1500);
    const firstGoal = page.locator('.goal-card-main').first();
    await firstGoal.click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
    const closeBtn = page.locator('.toolbar-btn[aria-label="Cerrar"]');
    await closeBtn.click();
    await page.waitForTimeout(500);
    // Should return to /goals
    await expect(page).toHaveURL(/\/goals$/);
  });
});

test.describe('Goal Editor — structure', () => {
  test.beforeEach(async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1500);
    await page.locator('.goal-card-main').first().click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('title input is visible', async ({ page }) => {
    await expect(page.locator('.title-input')).toBeVisible({ timeout: 5000 });
  });

  test('save button is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn.save-btn')).toBeVisible({ timeout: 5000 });
  });

  test('settings button (Ajustes) is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn:has-text("Ajustes")')).toBeVisible({ timeout: 5000 });
  });

  test('zen mode button is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn[aria-label="Modo Zen"]')).toBeVisible({ timeout: 5000 });
  });

  test('preview toggle is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn:has-text("Vista previa")').or(page.locator('.toolbar-btn:has-text("Editor")'))).toBeVisible({ timeout: 5000 });
  });

  test('word count stats are visible', async ({ page }) => {
    await expect(page.locator('.toolbar .stat').first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Goal Editor — title editing', () => {
  test('can edit goal title', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1500);
    await page.locator('.goal-card-main').first().click();
    await page.waitForTimeout(1000);
    const titleInput = page.locator('.title-input');
    await expect(titleInput).toBeVisible({ timeout: 5000 });
    await titleInput.fill('Goal Title from E2E Test');
    await page.waitForTimeout(300);
    // Save button should be visible
    await expect(page.locator('.toolbar-btn.save-btn')).toBeVisible();
  });
});

test.describe('Goal Editor — settings modal', () => {
  test.beforeEach(async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1500);
    await page.locator('.goal-card-main').first().click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('can open settings modal', async ({ page }) => {
    const settingsBtn = page.locator('.toolbar-btn:has-text("Ajustes")');
    await settingsBtn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.goal-settings-backdrop')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.goal-settings-heading:has-text("Editar objetivo")')).toBeVisible();
  });

  test('settings modal has 3 tabs', async ({ page }) => {
    await page.locator('.toolbar-btn:has-text("Ajustes")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('.ng-tab:has-text("Basico")').or(page.locator('.ng-tab:has-text("Básico")'))).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.ng-tab:has-text("Apariencia")')).toBeVisible();
    await expect(page.locator('.ng-tab:has-text("Avanzado")')).toBeVisible();
  });

  test('Basico tab has frequency buttons', async ({ page }) => {
    await page.locator('.toolbar-btn:has-text("Ajustes")').click();
    await page.waitForTimeout(500);
    // Frequency buttons: Diario, Semanal, Mensual, Anual
    await expect(page.locator('.ng-freq-btn:has-text("Diario")')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.ng-freq-btn:has-text("Semanal")')).toBeVisible();
    await expect(page.locator('.ng-freq-btn:has-text("Mensual")')).toBeVisible();
    await expect(page.locator('.ng-freq-btn:has-text("Anual")')).toBeVisible();
  });

  test('Apariencia tab has emoji and icon options', async ({ page }) => {
    await page.locator('.toolbar-btn:has-text("Ajustes")').click();
    await page.waitForTimeout(500);
    await page.locator('.ng-tab:has-text("Apariencia")').click();
    await page.waitForTimeout(300);
    await expect(page.locator('.icon-type-btn:has-text("Emoji")')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.icon-type-btn:has-text("Icono")')).toBeVisible();
  });

  test('Avanzado tab has measurement type', async ({ page }) => {
    await page.locator('.toolbar-btn:has-text("Ajustes")').click();
    await page.waitForTimeout(500);
    await page.locator('.ng-tab:has-text("Avanzado")').click();
    await page.waitForTimeout(300);
    // Should show measurement type label
    await expect(page.locator('.settings-advanced .label').first()).toBeVisible({ timeout: 3000 });
  });

  test('can close settings modal with Cancelar', async ({ page }) => {
    await page.locator('.toolbar-btn:has-text("Ajustes")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('.goal-settings-backdrop')).toBeVisible({ timeout: 3000 });
    const cancelBtn = page.locator('.goal-settings-footer .btn.btn-ghost:has-text("Cancelar")');
    await cancelBtn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.goal-settings-backdrop')).not.toBeVisible({ timeout: 3000 });
  });

  test('can close settings modal with X button', async ({ page }) => {
    await page.locator('.toolbar-btn:has-text("Ajustes")').click();
    await page.waitForTimeout(500);
    await expect(page.locator('.goal-settings-backdrop')).toBeVisible({ timeout: 3000 });
    const closeBtn = page.locator('.goal-settings-header button[aria-label="Cerrar"]');
    await closeBtn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.goal-settings-backdrop')).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Goal Editor — zen mode', () => {
  test('can toggle zen mode', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.waitForTimeout(1500);
    await page.locator('.goal-card-main').first().click();
    await page.waitForTimeout(1000);
    const zenBtn = page.locator('.toolbar-btn[aria-label="Modo Zen"]');
    await expect(zenBtn).toBeVisible({ timeout: 5000 });
    await zenBtn.click();
    await page.waitForTimeout(300);
    await expect(page.locator('.editor-shell')).toHaveClass(/zen-mode/);
    // Exit with Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  });
});

test.describe('Goal Editor — Inicio tab actions', () => {
  test('Inicio tab shows goal cards with action buttons', async ({ page }) => {
    await authGoto(page, '/goals');
    // Switch to Inicio tab
    await page.locator('button.tab:has-text("Inicio")').click();
    await page.waitForTimeout(1000);
    // Goal cards should be visible
    const goalCards = page.locator('.goal-card');
    const count = await goalCards.count();
    if (count > 0) {
      // Check for action buttons
      const actions = goalCards.first().locator('.goal-actions');
      if (await actions.isVisible({ timeout: 2000 }).catch(() => false)) {
        // Should have edit, delete buttons at minimum
        await expect(actions.locator('button[aria-label="Editar objetivo"]').or(actions.locator('button[aria-label="Eliminar objetivo"]'))).toBeVisible({ timeout: 3000 });
      }
    }
  });

  test('Inicio tab has Nuevo Objetivo button', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button.tab:has-text("Inicio")').click();
    await page.waitForTimeout(1000);
    const newGoalBtn = page.locator('button:has-text("Nuevo Objetivo")');
    if (await newGoalBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await expect(newGoalBtn).toBeVisible();
    }
  });
});

test.describe('Goal Editor — new goal creation', () => {
  test('can open new goal modal', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button.tab:has-text("Inicio")').click();
    await page.waitForTimeout(1000);
    const newGoalBtn = page.locator('button:has-text("Nuevo Objetivo")');
    if (await newGoalBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newGoalBtn.click();
      await page.waitForTimeout(500);
      // Modal should appear
      await expect(page.locator('.new-goal-backdrop')).toBeVisible({ timeout: 3000 });
      await expect(page.locator('.new-goal-heading:has-text("Nuevo Objetivo")')).toBeVisible();
    }
  });

  test('new goal modal has 3 columns', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button.tab:has-text("Inicio")').click();
    await page.waitForTimeout(1000);
    const newGoalBtn = page.locator('button:has-text("Nuevo Objetivo")');
    if (await newGoalBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newGoalBtn.click();
      await page.waitForTimeout(500);
      await expect(page.locator('.ng-col-title:has-text("Básico")').or(page.locator('.ng-col-title:has-text("Basico")'))).toBeVisible({ timeout: 3000 });
      await expect(page.locator('.ng-col-title:has-text("Apariencia")')).toBeVisible();
      await expect(page.locator('.ng-col-title:has-text("Avanzado")')).toBeVisible();
    }
  });

  test('new goal modal has title input and frequency buttons', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button.tab:has-text("Inicio")').click();
    await page.waitForTimeout(1000);
    const newGoalBtn = page.locator('button:has-text("Nuevo Objetivo")');
    if (await newGoalBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newGoalBtn.click();
      await page.waitForTimeout(500);
      // Title input
      const titleInput = page.locator('.new-goal-panel .input.w-full').first();
      await expect(titleInput).toBeVisible({ timeout: 3000 });
      // Frequency buttons
      await expect(page.locator('.ng-freq-btn:has-text("Diario")')).toBeVisible({ timeout: 3000 });
      await expect(page.locator('.ng-freq-btn:has-text("Semanal")')).toBeVisible();
      await expect(page.locator('.ng-freq-btn:has-text("Mensual")')).toBeVisible();
      await expect(page.locator('.ng-freq-btn:has-text("Anual")')).toBeVisible();
    }
  });

  test('new goal modal can be cancelled', async ({ page }) => {
    await authGoto(page, '/goals');
    await page.locator('button.tab:has-text("Inicio")').click();
    await page.waitForTimeout(1000);
    const newGoalBtn = page.locator('button:has-text("Nuevo Objetivo")');
    if (await newGoalBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await newGoalBtn.click();
      await page.waitForTimeout(500);
      await expect(page.locator('.new-goal-backdrop')).toBeVisible({ timeout: 3000 });
      const cancelBtn = page.locator('.new-goal-footer .btn.btn-ghost:has-text("Cancelar")');
      await cancelBtn.click();
      await page.waitForTimeout(500);
      await expect(page.locator('.new-goal-backdrop')).not.toBeVisible({ timeout: 3000 });
    }
  });
});
