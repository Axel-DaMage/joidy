import { test, expect, authGoto } from './helpers/auth';

/**
 * AI feature — comprehensive E2E tests.
 * Covers: chat interface, suggestion chips, input, dev mode panel.
 */
test.describe('AI — page structure', () => {
  test('ai page loads with title', async ({ page }) => {
    await authGoto(page, '/ai');
    await expect(page.locator('text=/inteligencia artificial/i')).toBeVisible();
  });

  test('IA active status is shown', async ({ page }) => {
    await authGoto(page, '/ai');
    await expect(page.locator('text=/IA activa/i')).toBeVisible({ timeout: 5000 });
  });

  test('chat interface is visible', async ({ page }) => {
    await authGoto(page, '/ai');
    await expect(page.locator('text=/asistente joidy/i')).toBeVisible();
  });

  test('message input textarea is visible', async ({ page }) => {
    await authGoto(page, '/ai');
    const textarea = page.locator('textarea');
    await expect(textarea).toBeVisible({ timeout: 5000 });
  });

  test('send button is visible', async ({ page }) => {
    await authGoto(page, '/ai');
    await expect(page.locator('.send-btn')).toBeVisible();
  });
});

test.describe('AI — suggestion chips', () => {
  test('all 4 suggestion chips are visible', async ({ page }) => {
    await authGoto(page, '/ai');
    await expect(page.locator('button.suggestion-chip:has-text("¿Qué debería aprender esta semana?")')).toBeVisible();
    await expect(page.locator('button.suggestion-chip:has-text("Ayúdame a definir una nueva meta")')).toBeVisible();
    await expect(page.locator('button.suggestion-chip:has-text("¿Cómo organizo mejor mis notas?")')).toBeVisible();
    await expect(page.locator('button.suggestion-chip:has-text("Dame un resumen de mi progreso")')).toBeVisible();
  });

  test('clicking a suggestion chip fills the input or sends message', async ({ page }) => {
    await authGoto(page, '/ai');
    const chip = page.locator('button.suggestion-chip').first();
    await chip.click();
    await page.waitForTimeout(1000);
    // The chip either fills the textarea or sends the message directly
    const textarea = page.locator('textarea');
    const value = await textarea.inputValue();
    const messages = page.locator('.chat-message, .message, [class*="message"]');
    const msgCount = await messages.count();
    // Either the text was filled in the input, or a message was sent
    expect(value.length > 0 || msgCount > 0).toBeTruthy();
  });
});

test.describe('AI — chat interaction', () => {
  test('can type a message', async ({ page }) => {
    await authGoto(page, '/ai');
    const textarea = page.locator('textarea');
    await textarea.fill('Test message from E2E');
    await expect(textarea).toHaveValue('Test message from E2E');
  });

  test('can send a message with Enter key', async ({ page }) => {
    await authGoto(page, '/ai');
    const textarea = page.locator('textarea');
    await textarea.fill('Test message from E2E');
    await textarea.press('Enter');
    // Wait for response or loading indicator
    await page.waitForTimeout(2000);
    // A message should appear (user or AI)
    const messages = page.locator('.chat-message, .message, [class*="message"]');
    // At minimum, the input should be cleared after sending
    const inputValue = await textarea.inputValue();
    // Message was either sent (input cleared) or is being processed
    expect(inputValue === '' || messages.count() > 0).toBeTruthy();
  });
});

test.describe('AI — dev mode panel', () => {
  test('dev mode panel is visible when dev mode is on', async ({ page }) => {
    await authGoto(page, '/ai');
    // With dev mode enabled, the AI page shows a dev status panel
    // Check for "Modo dev" text or service status section
    const devPanel = page.locator('text=/modo dev/i');
    await expect(devPanel.first()).toBeVisible({ timeout: 5000 });
  });
});
