import { test, expect, authGoto } from './helpers/auth';

/**
 * Note Editor — comprehensive E2E tests.
 * Covers: open editor, title editing, content editing, tags, formatting,
 * view modes (preview/WYSIWYG/zen), export dropdown, delete flow.
 *
 * Selector note (#1476): the notes list default view is the FILE TREE
 * (NotesListBody, viewMode 'tree'), not card grid — notes are `.file-row`
 * tree items; clicking one opens NoteEditor inside `.editor-panel`.
 */
test.describe('Note Editor — open/close', () => {
  test('can open a note from the list', async ({ page }) => {
    await authGoto(page, '/notes');
    const firstNote = page.locator('.file-row').first();
    await expect(firstNote).toBeVisible({ timeout: 5000 });
    await firstNote.click();
    // Editor shell should be visible
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('can close editor with close button', async ({ page }) => {
    await authGoto(page, '/notes');
    const firstNote = page.locator('.file-row').first();
    await firstNote.click();
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
    const closeBtn = page.locator('.toolbar-btn[aria-label="Cerrar"]');
    await closeBtn.click();
    await expect(page.locator('.editor-shell')).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe('Note Editor — structure', () => {
  test.beforeEach(async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('all editor structure elements are visible', async ({ page }) => {
    await expect(page.locator('.title-input')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.tag-input')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn.save-btn')).toBeVisible({ timeout: 5000 });
    // Format toolbar
    await expect(page.locator('.toolbar-btn[aria-label="Negrita"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Cursiva"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Título 1"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Enlace"]')).toBeVisible({ timeout: 5000 });
    // Word/char count stats
    await expect(page.locator('.toolbar .stat').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn:has-text("Exportar")')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn.danger-btn[aria-label="Eliminar nota"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Note Editor — title editing', () => {
  test('can edit the note title', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const titleInput = page.locator('.title-input');
    await expect(titleInput).toBeVisible({ timeout: 5000 });
    await titleInput.fill('Test Title from E2E');
    // The save button should become active or show "Guardar"
    await expect(page.locator('.toolbar-btn.save-btn')).toBeVisible();
  });
});

test.describe('Note Editor — tag input', () => {
  test('can add a tag', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const tagInput = page.locator('.tag-input');
    await expect(tagInput).toBeVisible({ timeout: 5000 });
    await tagInput.fill('e2e-test-tag');
    await tagInput.press('Enter');
    // The tag chip should appear
    await expect(page.locator('.tag-chip:has-text("e2e-test-tag")')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Note Editor — view modes', () => {
  test.beforeEach(async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('can toggle preview mode', async ({ page }) => {
    const previewBtn = page.locator('.toolbar-btn:has-text("Vista previa")');
    if (await previewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await previewBtn.click();
      // Preview panel should be visible
      await expect(page.locator('.preview')).toBeVisible({ timeout: 3000 });
      // Toggle back
      const editorBtn = page.locator('.toolbar-btn:has-text("Editor")');
      if (await editorBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await editorBtn.click();
      }
    }
  });

  test('can toggle zen mode', async ({ page }) => {
    const zenBtn = page.locator('.toolbar-btn[aria-label="Modo Zen"]');
    await expect(zenBtn).toBeVisible({ timeout: 5000 });
    await zenBtn.click();
    // Editor shell should have zen-mode class
    await expect(page.locator('.editor-shell')).toHaveClass(/zen-mode/);
    // Exit zen mode with Escape
    await page.keyboard.press('Escape');
  });
});

test.describe('Note Editor — export dropdown', () => {
  test('export dropdown shows 3 options', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const exportBtn = page.locator('.toolbar-btn:has-text("Exportar")');
    await expect(exportBtn).toBeVisible({ timeout: 5000 });
    await exportBtn.click();
    // Dropdown menu should appear with 3 options
    await expect(page.locator('.export-dropdown-menu')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.dropdown-item:has-text("Descargar Markdown")')).toBeVisible();
    await expect(page.locator('.dropdown-item:has-text("Descargar HTML")')).toBeVisible();
    await expect(page.locator('.dropdown-item:has-text("Copiar Markdown")')).toBeVisible();
    // Close dropdown
    await page.keyboard.press('Escape');
  });
});

test.describe('Note Editor — delete flow', () => {
  test('delete button shows confirmation modal', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const deleteBtn = page.locator('.toolbar-btn.danger-btn[aria-label="Eliminar nota"]');
    await expect(deleteBtn).toBeVisible({ timeout: 5000 });
    await deleteBtn.click();
    // Confirmation modal (ModalDialog) should appear — the old
    // .delete-confirm-bar was replaced by NotesDeleteModal (#210).
    const modal = page.locator('.modal-overlay .modal');
    await expect(modal).toBeVisible({ timeout: 3000 });
    await expect(modal.locator('.modal-title')).toHaveText('Eliminar');
    await expect(modal.locator('.delete-modal-desc')).toHaveText(
      'Esta acción no se puede deshacer.'
    );
    // Cancel
    await modal.locator('.btn-ghost:has-text("Cancelar")').click();
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Note Editor — navigation', () => {
  test('prev/next navigation buttons are visible', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    await expect(page.locator('.toolbar-btn[aria-label="Nota anterior"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Siguiente nota"]')).toBeVisible({ timeout: 5000 });
  });

  test('can navigate to next note', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const nextBtn = page.locator('.toolbar-btn[aria-label="Siguiente nota"]');
    // Click next if not disabled
    const isDisabled = await nextBtn.isDisabled().catch(() => true);
    if (!isDisabled) {
      await nextBtn.click();
      // Editor should still be visible with different content
      await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe('Note Editor — icon customization', () => {
  test('icon customization button is visible', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const iconBtn = page.locator('.note-icon-btn[aria-label="Personalizar icono"]');
    await expect(iconBtn).toBeVisible({ timeout: 5000 });
  });

  test('can open icon customization modal', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.locator('.file-row').first().click();
    const iconBtn = page.locator('.note-icon-btn[aria-label="Personalizar icono"]');
    await iconBtn.click();
    // Modal should appear
    await expect(page.locator('.folder-modal-title:has-text("Personalizar icono")')).toBeVisible({ timeout: 3000 });
    // Close
    const closeBtn = page.locator('.folder-modal-btns button:has-text("Cerrar")');
    if (await closeBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await closeBtn.click();
    } else {
      await page.keyboard.press('Escape');
    }
  });
});
