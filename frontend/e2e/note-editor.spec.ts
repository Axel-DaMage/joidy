import { test, expect, authGoto } from './helpers/auth';

/**
 * Note Editor — comprehensive E2E tests.
 * Covers: open editor, title editing, content editing, tags, formatting,
 * view modes (preview/WYSIWYG/zen), export dropdown, delete flow.
 */
test.describe('Note Editor — open/close', () => {
  test('can open a note from the list', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    const firstNote = page.locator('.note-card').first();
    await expect(firstNote).toBeVisible({ timeout: 5000 });
    await firstNote.click();
    await page.waitForTimeout(1000);
    // Editor shell should be visible
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('can close editor with close button', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    const firstNote = page.locator('.note-card').first();
    await firstNote.click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
    const closeBtn = page.locator('.toolbar-btn[aria-label="Cerrar"]');
    await closeBtn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('.editor-shell')).not.toBeVisible({ timeout: 5000 });
  });
});

test.describe('Note Editor — structure', () => {
  test.beforeEach(async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('title input is visible', async ({ page }) => {
    await expect(page.locator('.title-input')).toBeVisible({ timeout: 5000 });
  });

  test('tag input is visible', async ({ page }) => {
    await expect(page.locator('.tag-input')).toBeVisible({ timeout: 5000 });
  });

  test('save button is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn.save-btn')).toBeVisible({ timeout: 5000 });
  });

  test('format toolbar buttons are visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn[aria-label="Negrita"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Cursiva"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Título 1"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Enlace"]')).toBeVisible({ timeout: 5000 });
  });

  test('word and char count stats are visible', async ({ page }) => {
    await expect(page.locator('.toolbar .stat').first()).toBeVisible({ timeout: 5000 });
  });

  test('export button is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn:has-text("Exportar")')).toBeVisible({ timeout: 5000 });
  });

  test('delete button is visible', async ({ page }) => {
    await expect(page.locator('.toolbar-btn.danger-btn[aria-label="Eliminar nota"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Note Editor — title editing', () => {
  test('can edit the note title', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
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
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    const tagInput = page.locator('.tag-input');
    await expect(tagInput).toBeVisible({ timeout: 5000 });
    await tagInput.fill('e2e-test-tag');
    await tagInput.press('Enter');
    await page.waitForTimeout(500);
    // The tag chip should appear
    await expect(page.locator('.tag-chip:has-text("e2e-test-tag")')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Note Editor — view modes', () => {
  test.beforeEach(async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 5000 });
  });

  test('can toggle preview mode', async ({ page }) => {
    const previewBtn = page.locator('.toolbar-btn:has-text("Vista previa")');
    if (await previewBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await previewBtn.click();
      await page.waitForTimeout(500);
      // Preview panel should be visible
      await expect(page.locator('.preview')).toBeVisible({ timeout: 3000 });
      // Toggle back
      const editorBtn = page.locator('.toolbar-btn:has-text("Editor")');
      if (await editorBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await editorBtn.click();
        await page.waitForTimeout(300);
      }
    }
  });

  test('can toggle zen mode', async ({ page }) => {
    const zenBtn = page.locator('.toolbar-btn[aria-label="Modo Zen"]');
    await expect(zenBtn).toBeVisible({ timeout: 5000 });
    await zenBtn.click();
    await page.waitForTimeout(300);
    // Editor shell should have zen-mode class
    await expect(page.locator('.editor-shell')).toHaveClass(/zen-mode/);
    // Exit zen mode with Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  });
});

test.describe('Note Editor — export dropdown', () => {
  test('export dropdown shows 3 options', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    const exportBtn = page.locator('.toolbar-btn:has-text("Exportar")');
    await expect(exportBtn).toBeVisible({ timeout: 5000 });
    await exportBtn.click();
    await page.waitForTimeout(500);
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
  test('delete button shows confirmation bar', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    const deleteBtn = page.locator('.toolbar-btn.danger-btn[aria-label="Eliminar nota"]');
    await expect(deleteBtn).toBeVisible({ timeout: 5000 });
    await deleteBtn.click();
    await page.waitForTimeout(500);
    // Confirmation bar should appear
    await expect(page.locator('.delete-confirm-bar')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('.delete-confirm-text:has-text("¿Eliminar esta nota?")')).toBeVisible();
    // Cancel
    await page.locator('.btn-cancel:has-text("Cancelar")').click();
    await page.waitForTimeout(300);
    await expect(page.locator('.delete-confirm-bar')).not.toBeVisible({ timeout: 3000 });
  });
});

test.describe('Note Editor — navigation', () => {
  test('prev/next navigation buttons are visible', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    await expect(page.locator('.toolbar-btn[aria-label="Nota anterior"]')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.toolbar-btn[aria-label="Siguiente nota"]')).toBeVisible({ timeout: 5000 });
  });

  test('can navigate to next note', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    const nextBtn = page.locator('.toolbar-btn[aria-label="Siguiente nota"]');
    // Click next if not disabled
    const isDisabled = await nextBtn.isDisabled().catch(() => true);
    if (!isDisabled) {
      await nextBtn.click();
      await page.waitForTimeout(1000);
      // Editor should still be visible with different content
      await expect(page.locator('.editor-shell')).toBeVisible({ timeout: 3000 });
    }
  });
});

test.describe('Note Editor — icon customization', () => {
  test('icon customization button is visible', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    const iconBtn = page.locator('.note-icon-btn[aria-label="Personalizar icono"]');
    await expect(iconBtn).toBeVisible({ timeout: 5000 });
  });

  test('can open icon customization modal', async ({ page }) => {
    await authGoto(page, '/notes');
    await page.waitForTimeout(1500);
    await page.locator('.note-card').first().click();
    await page.waitForTimeout(1000);
    const iconBtn = page.locator('.note-icon-btn[aria-label="Personalizar icono"]');
    await iconBtn.click();
    await page.waitForTimeout(500);
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
