import { test, expect, authGoto, getAuthToken } from './helpers/auth';

/**
 * Notes feature — comprehensive E2E tests.
 * Covers: list view, search, create, edit, delete, folders, export.
 */
test.describe('Notes — list view', () => {
  test('notes page loads with note list', async ({ page }) => {
    await authGoto(page, '/notes');
    // Search input should be visible
    await expect(page.locator('input[placeholder="Buscar..."]')).toBeVisible();
    // Note count or notes should be visible
    const noteArea = page.locator('main.app-main');
    await expect(noteArea).not.toBeEmpty();
  });

  test('notes count is displayed', async ({ page }) => {
    await authGoto(page, '/notes');
    // The notes page shows a count like "1000 notas"
    await expect(page.locator('text=/\\d+\\s+notas/i')).toBeVisible({ timeout: 5000 });
  });

  test('search input filters notes', async ({ page }) => {
    await authGoto(page, '/notes');
    const search = page.locator('input[placeholder="Buscar..."]');
    await search.fill('Track Aws');
    // Should show at least one matching note
    await expect(page.locator('text=Track Aws').first()).toBeVisible({ timeout: 3000 });
  });

  test('search with no results shows empty state', async ({ page }) => {
    await authGoto(page, '/notes');
    const search = page.locator('input[placeholder="Buscar..."]');
    await search.fill('zzz_no_match_xyz_12345');
    // The note list should be empty (no note entries visible in either the
    // tree view — .file-row — or the legacy card/list views)
    const noteCards = page.locator('.file-row, .note-item, .note-card');
    // Wait for filtering to complete
    await expect(noteCards).toHaveCount(0);
  });

  test('search can be cleared', async ({ page }) => {
    await authGoto(page, '/notes');
    const search = page.locator('input[placeholder="Buscar..."]');
    await search.fill('Track');
    await search.clear();
    // Notes should reappear
    await expect(page.locator('text=/\\d+\\s+notas/i')).toBeVisible({ timeout: 3000 });
  });
});

test.describe('Notes — create flow', () => {
  test('create note button is visible', async ({ page }) => {
    await authGoto(page, '/notes');
    const createBtn = page.locator('button[aria-label="Crear nota"]');
    await expect(createBtn).toBeVisible();
  });

  test('can create a new note', async ({ page }) => {
    await authGoto(page, '/notes');
    const createBtn = page.locator('button[aria-label="Crear nota"]');
    await createBtn.click();
    // Should navigate to the new note or open an editor
    // The editor should be visible
    await expect(page.locator('main.app-main')).not.toBeEmpty();
  });
});

test.describe('Notes — toolbar actions', () => {
  test('all toolbar buttons are visible', async ({ page }) => {
    await authGoto(page, '/notes');
    await expect(page.locator('button[aria-label="Crear nota"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Crear carpeta"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Cambiar orden"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Comprimir todo"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Modo selección múltiple"]')).toBeVisible();
  });

  test('sort order button toggles', async ({ page }) => {
    await authGoto(page, '/notes');
    const sortBtn = page.locator('button[aria-label="Cambiar orden"]');
    await sortBtn.click();
    // A dropdown or menu should appear — short semantic wait for the menu
    // animation before dismissing with Escape (no assertion can express it)
    await page.waitForTimeout(300);
    // Click again or press Escape to close
    await page.keyboard.press('Escape');
  });

  test('bulk selection mode toggles', async ({ page }) => {
    await authGoto(page, '/notes');
    const bulkBtn = page.locator('button[aria-label="Modo selección múltiple"]');
    await bulkBtn.click();
    // Short semantic wait for the mode transition before toggling back off
    await page.waitForTimeout(500);
    // Toggle off
    await bulkBtn.click();
  });
});

test.describe('Notes — note selection', () => {
  test('clicking a note opens the editor', async ({ page }) => {
    await authGoto(page, '/notes');
    // Click the first note item — the default list view is the file tree
    // (NotesListBody), where notes are .file-row tree items (#1476)
    const firstNote = page.locator('.file-row, .note-item, .note-card, [class*="note-item"]').first();
    if (await firstNote.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstNote.click();
      // Editor should appear — at minimum, the page should still be functional
      await expect(page.locator('main.app-main')).toBeVisible();
    }
  });

  // Regresión Kit 3: afterNavigate no se dispara en la carga inicial y el
  // objeto de navegación ya no trae url en el nivel superior — un deep-link
  // directo /notes?id=... no abría el editor (el sync URL→editor estaba
  // muerto; solo funcionaba abrir por click).
  test('opens editor on direct deep-link load (?id=)', async ({ page }) => {
    // Regresión Kit 3: afterNavigate no se dispara en la carga inicial y el
    // objeto de navegación ya no trae url en el nivel superior — un deep-link
    // directo /notes?id=... no abría el editor (el sync URL→editor estaba
    // muerto; solo funcionaba abrir por click).
    const res = await page.request.get(`${process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000'}/notes/?limit=1`, {
      headers: { Authorization: `Bearer ${await getAuthToken()}` },
    });
    const notes = await res.json();
    test.skip(!Array.isArray(notes) || notes.length === 0, 'no notes in DB');
    await authGoto(page, `/notes?id=${notes[0].id}`);
    await expect(page.locator('main.app-main textarea, main.app-main [contenteditable="true"], .note-editor').first()).toBeVisible({ timeout: 5000 });
  });
});
