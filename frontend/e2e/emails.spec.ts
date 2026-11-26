import { test, expect, authGoto, getAuthToken } from './helpers/auth';
import type { Page } from '@playwright/test';

/**
 * Emails tray — E2E tests (#1255).
 *
 * The /emails inbox is populated by the n8n Gmail workflow via
 * `POST /emails/` (upsert semantics). Tests seed their own messages with
 * unique subjects (E2E pattern, cleaned up by the global teardown) and use
 * the search box to isolate them from any pre-existing mail.
 *
 * Locale: Spanish (es-ES) — set in the auth helper.
 */

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';

interface SeedEmailInput {
  subject: string;
  unread?: boolean;
  important?: boolean;
}

/** Push an email through the real n8n ingest endpoint. */
async function seedEmail(page: Page, runId: string, input: SeedEmailInput): Promise<number> {
  const res = await page.request.post(`${API_BASE}/emails/`, {
    headers: { Authorization: `Bearer ${await getAuthToken()}` },
    data: {
      account: 'e2e@joidy.test',
      gmail_id: `e2e-${runId}-${input.subject}`,
      subject: input.subject,
      sender: 'E2E Robot <e2e@joidy.test>',
      snippet: `E2E snippet ${runId}`,
      unread: input.unread ?? true,
      important: input.important ?? false,
      received_at: new Date().toISOString(),
    },
  });
  if (!res.ok()) throw new Error(`seedEmail failed: ${res.status()} ${await res.text()}`);
  return (await res.json()).id;
}

/** Search for a unique run token so only this test's mail is listed. */
async function searchRun(page: Page, runId: string): Promise<void> {
  // The input debounces 300ms, then issues GET /emails/?…q=<runId> —
  // wait for that exact response instead of a fixed sleep.
  const results = page.waitForResponse(
    (r) =>
      r.request().method() === 'GET' &&
      r.url().includes('/emails/') &&
      r.url().includes(`q=${encodeURIComponent(runId)}`)
  );
  await page.locator('.search-input').fill(runId);
  await results;
}

test.describe('Emails — page structure', () => {
  test('emails page renders header, filters and search', async ({ page }) => {
    await authGoto(page, '/emails');
    await expect(page.locator('.emails-page')).toBeVisible();
    await expect(page.locator('.emails-page h3')).toHaveText('Correos');
    await expect(page.locator('.filter-chip:has-text("No leídos")')).toBeVisible();
    await expect(page.locator('.filter-chip:has-text("Importantes")')).toBeVisible();
    await expect(page.locator('.search-input')).toBeVisible();
  });
});

test.describe('Emails — empty states', () => {
  test('shows the empty-inbox state when no mail is synced', async ({ page }) => {
    const res = await page.request.get(`${API_BASE}/emails/accounts`, {
      headers: { Authorization: `Bearer ${await getAuthToken()}` },
    });
    const accounts = res.ok() ? await res.json() : [];
    const total = Array.isArray(accounts)
      ? accounts.reduce((sum: number, a: { total?: number }) => sum + (a.total ?? 0), 0)
      : 0;
    test.skip(total > 0, 'inbox already has mail — empty state not applicable');

    await authGoto(page, '/emails');
    await expect(page.locator('.empty-state-title')).toHaveText(
      'Aún no hay correos sincronizados'
    );
  });

  test('search with no matches shows the empty-unread state', async ({ page }) => {
    // absoluteTotal must be > 0 for the filtered-empty state to render.
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} filler` });
    await authGoto(page, '/emails');
    await searchRun(page, `no-such-mail-${runId}`);
    // Default "No leídos" filter is on → unread-specific empty title
    await expect(page.locator('.empty-state-title')).toHaveText(
      'Bandeja al día: cero no leídos'
    );
    // With the unread filter off, the generic no-results state shows
    await page.locator('.filter-chip:has-text("No leídos")').click();
    await expect(page.locator('.empty-state-title')).toHaveText(
      'Sin resultados para esa búsqueda'
    );
  });
});

test.describe('Emails — list and interactions', () => {
  test('renders seeded email rows with sender and unread marker', async ({ page }) => {
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} Unread` });
    await authGoto(page, '/emails');
    await searchRun(page, runId);

    const item = page.locator('.email-item', { hasText: `E2E Mail ${runId}` });
    await expect(item).toBeVisible();
    await expect(item.locator('.sender')).toHaveText('E2E Robot');
    await expect(item.locator('.unread-dot')).toBeVisible();
  });

  test('unread filter hides read mail until toggled off', async ({ page }) => {
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} Read`, unread: false });
    await authGoto(page, '/emails');
    await searchRun(page, runId);
    // Read mail is filtered out by the default "No leídos" filter
    await expect(page.locator('.email-item', { hasText: runId })).toHaveCount(0);
    await page.locator('.filter-chip:has-text("No leídos")').click();
    await expect(page.locator('.email-item', { hasText: runId })).toHaveCount(1);
  });

  test('mark as read removes the unread marker', async ({ page }) => {
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} Mark` });
    await authGoto(page, '/emails');
    await searchRun(page, runId);

    const item = page.locator('.email-item', { hasText: runId });
    await expect(item).toHaveClass(/unread/);
    await item.locator('.email-ops button:has-text("Marcar leído")').click();
    await expect(item).not.toHaveClass(/unread/);
    await expect(item.locator('.unread-dot')).toHaveCount(0);
  });

  test('important toggle marks the subject with a star', async ({ page }) => {
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} Star` });
    await authGoto(page, '/emails');
    await searchRun(page, runId);

    const item = page.locator('.email-item', { hasText: runId });
    await expect(item.locator('.subject .star-wrap')).toHaveCount(0);
    await item.locator('.email-ops button[title="Cambiar importancia"]').click();
    await expect(item.locator('.subject .star-wrap')).toBeVisible();
  });

  test('delete removes the email from the list', async ({ page }) => {
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} Delete` });
    await authGoto(page, '/emails');
    await searchRun(page, runId);

    const item = page.locator('.email-item', { hasText: runId });
    await expect(item).toBeVisible();
    await item.locator('.email-ops button:has-text("×")').click();
    await expect(item).toHaveCount(0);
  });

  test('account chip filters by the seeded account', async ({ page }) => {
    const runId = `${Date.now()}`;
    await seedEmail(page, runId, { subject: `E2E Mail ${runId} Account` });
    await authGoto(page, '/emails');
    await searchRun(page, runId);
    await expect(page.locator('.email-item', { hasText: runId })).toHaveCount(1);

    const chip = page.locator('.account-chips .filter-chip:has-text("e2e@joidy.test")');
    await expect(chip).toBeVisible();
    await chip.click();
    await expect(chip).toHaveClass(/active/);
    await expect(page.locator('.email-item', { hasText: runId })).toHaveCount(1);
  });
});
