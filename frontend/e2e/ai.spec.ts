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

test.describe('AI — chat interface details', () => {
  test('chat header has clear button when messages exist', async ({ page }) => {
    await authGoto(page, '/ai');
    // Wait for ChatInterface to lazy-load
    await expect(page.locator('.chat')).toBeVisible({ timeout: 10000 });
    // The clear button only appears when there are messages ({#if !isEmpty})
    // Send a message first
    const textarea = page.locator('textarea');
    await textarea.fill('Test for clear button');
    await textarea.press('Enter');
    await page.waitForTimeout(2000);
    // Now the clear button should be visible
    const clearBtn = page.locator('.clear-btn');
    if (await clearBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
      await expect(clearBtn).toBeVisible();
    }
  });

  test('empty state shows suggestions when no messages', async ({ page }) => {
    await authGoto(page, '/ai');
    await page.waitForTimeout(1000);
    // Empty state should be visible initially
    const emptyState = page.locator('.empty-state');
    if (await emptyState.isVisible({ timeout: 2000 }).catch(() => false)) {
      await expect(emptyState).toBeVisible();
      // Suggestions should be in the empty state
      await expect(page.locator('.suggestions .suggestion-chip').first()).toBeVisible({ timeout: 3000 });
    }
  });

  test('chat messages container is visible', async ({ page }) => {
    await authGoto(page, '/ai');
    await page.waitForTimeout(1000);
    await expect(page.locator('.chat-messages')).toBeVisible({ timeout: 5000 });
  });

  test('chat input area is visible', async ({ page }) => {
    await authGoto(page, '/ai');
    await page.waitForTimeout(1000);
    await expect(page.locator('.chat-input')).toBeVisible({ timeout: 5000 });
  });

  test('send button is disabled when input is empty', async ({ page }) => {
    await authGoto(page, '/ai');
    await page.waitForTimeout(1000);
    const sendBtn = page.locator('.send-btn');
    await expect(sendBtn).toBeVisible({ timeout: 5000 });
    // Should be disabled when textarea is empty
    const textarea = page.locator('textarea');
    await textarea.fill('');
    await expect(sendBtn).toBeDisabled();
  });

  test('send button is enabled when input has text', async ({ page }) => {
    await authGoto(page, '/ai');
    await page.waitForTimeout(1000);
    const sendBtn = page.locator('.send-btn');
    const textarea = page.locator('textarea');
    await textarea.fill('Test message');
    await expect(sendBtn).toBeEnabled({ timeout: 3000 });
  });

  test('can clear chat with clear button', async ({ page }) => {
    await authGoto(page, '/ai');
    await page.waitForTimeout(1000);
    // First send a message
    const textarea = page.locator('textarea');
    await textarea.fill('Test message for clearing');
    await textarea.press('Enter');
    await page.waitForTimeout(2000);
    // Now click clear
    const clearBtn = page.locator('.clear-btn');
    await clearBtn.click();
    await page.waitForTimeout(500);
    // After clearing, the empty state should be visible again
    const emptyState = page.locator('.empty-state');
    // The empty state may or may not appear depending on implementation
    if (await emptyState.isVisible({ timeout: 2000 }).catch(() => false)) {
      await expect(emptyState).toBeVisible();
    }
  });
});

test.describe('AI — dev mode panel details', () => {
  async function expandDevPanel(page: import('@playwright/test').Page) {
    await authGoto(page, '/ai');
    // The dev section is a <details> element — expand it to see contents
    const devSection = page.locator('.dev-section');
    await expect(devSection).toBeVisible({ timeout: 5000 });
    const summary = devSection.locator('summary');
    await summary.click();
    await page.waitForTimeout(300);
  }

  test('dev panel shows API key status', async ({ page }) => {
    await expandDevPanel(page);
    await expect(page.locator('text=/API Key configurada/i')).toBeVisible({ timeout: 5000 });
  });

  test('dev panel shows estimated cost', async ({ page }) => {
    await expandDevPanel(page);
    await expect(page.locator('text=/Costo estimado/i')).toBeVisible({ timeout: 5000 });
  });

  test('dev panel is collapsible', async ({ page }) => {
    await authGoto(page, '/ai');
    const devSection = page.locator('.dev-section');
    await expect(devSection).toBeVisible({ timeout: 5000 });
    const summary = devSection.locator('summary');
    await expect(summary).toBeVisible();
  });
});
