import { test, expect, authGoto, getAuthToken } from './helpers/auth';
import type { Page } from '@playwright/test';

/**
 * Calendar feature — E2E tests (#1255).
 *
 * The calendar has two runtime paths:
 *  - Google-free: no Google account linked → the page renders a
 *    "not connected" empty state. Covered deterministically by stubbing
 *    the status endpoint (CI also hits this path for real).
 *  - Connected: the Google read endpoints are stubbed (status → connected,
 *    events → []) so the full calendar UI renders while tasks are exercised
 *    against the real `/calendar/tasks` API (local DB, no Google needed).
 *    This mirrors the shipped "AI disabled / Google-free" mode where tasks
 *    still work without the AI planner or a linked account.
 *
 * Locale: Spanish (es-ES) — set in the auth helper.
 */

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';

/** Stub the Google calendar endpoints as "linked, nothing cached". */
async function stubGoogleConnected(page: Page): Promise<void> {
  await page.route('**/integrations/google/calendar/status', (route) =>
    route.fulfill({
      json: {
        connected: true,
        calendars: 0,
        cached_events: 0,
        last_synced_at: new Date().toISOString(),
      },
    })
  );
  await page.route('**/integrations/google/calendar/events**', (route) =>
    route.fulfill({ json: [] })
  );
  await page.route('**/integrations/google/calendar/sync', (route) =>
    route.fulfill({ json: { synced_at: new Date().toISOString(), calendars: [] } })
  );
}

/** Stub the status endpoint as "not linked" for the empty-state path. */
async function stubGoogleDisconnected(page: Page): Promise<void> {
  await page.route('**/integrations/google/calendar/status', (route) =>
    route.fulfill({
      json: { connected: false, calendars: 0, cached_events: 0, last_synced_at: null },
    })
  );
}

function localDayKey(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Create a calendar task via the real API (faster + no UI coupling). */
async function seedTask(
  page: Page,
  title: string,
  date: string | null
): Promise<number> {
  const res = await page.request.post(`${API_BASE}/calendar/tasks`, {
    headers: { Authorization: `Bearer ${await getAuthToken()}` },
    data: { title, date },
  });
  if (!res.ok()) throw new Error(`seedTask failed: ${res.status()} ${await res.text()}`);
  return (await res.json()).id;
}

test.describe('Calendar — Google-free path', () => {
  test('shows the not-connected empty state when Google is not linked', async ({
    page,
  }) => {
    await stubGoogleDisconnected(page);
    await authGoto(page, '/calendar');
    await expect(page.locator('.calendar-page')).toBeVisible();
    await expect(page.locator('.empty-state-title')).toHaveText('Google no está conectado');
    // The calendar body must not render in this path.
    await expect(page.locator('.day-grid')).toHaveCount(0);
  });
});

test.describe('Calendar — month grid', () => {
  test.beforeEach(async ({ page }) => {
    await stubGoogleConnected(page);
  });

  test('month grid renders with weekday headers and day cells', async ({ page }) => {
    await authGoto(page, '/calendar');
    await expect(page.locator('.calendar-page')).toBeVisible();
    await expect(page.locator('.view-switcher')).toBeVisible();
    // 7 weekday labels (Lun..Dom in es locale)
    await expect(page.locator('.weekday-row .weekday')).toHaveCount(7);
    // A month grid always renders at least 28 day cells
    const cells = page.locator('.day-grid .day-cell');
    await expect(cells.first()).toBeVisible();
    expect(await cells.count()).toBeGreaterThanOrEqual(28);
    // Today is highlighted
    await expect(page.locator('.day-cell.today')).toBeVisible();
  });

  test('day detail prompts to pick a day and shows detail on click', async ({
    page,
  }) => {
    await authGoto(page, '/calendar');
    await expect(page.locator('.day-detail h4')).toHaveText('Selecciona un día');
    await page.locator('.day-cell.today').click();
    await expect(page.locator('.day-cell.today')).toHaveClass(/selected/);
    // Quick-add form appears once a day is selected
    await expect(page.locator('.quick-add')).toBeVisible();
    await expect(
      page.locator('.quick-add input[aria-label="Nueva tarea… (título + Enter)"]')
    ).toBeVisible();
  });
});

test.describe('Calendar — views', () => {
  test.beforeEach(async ({ page }) => {
    await stubGoogleConnected(page);
    // Always start from the month view — the last selection persists in
    // localStorage across tests.
    await page.addInitScript(() => localStorage.setItem('joidy-calendar-view', 'month'));
    await authGoto(page, '/calendar');
  });

  test('switches to week view', async ({ page }) => {
    await page.locator('.view-switcher button:has-text("Semana")').click();
    await expect(page.locator('.week-grid')).toBeVisible();
    await expect(page.locator('.week-col')).toHaveCount(7);
    await expect(
      page.locator('.view-switcher button:has-text("Semana")')
    ).toHaveAttribute('aria-pressed', 'true');
  });

  test('switches to agenda view', async ({ page }) => {
    await page.locator('.view-switcher button:has-text("Agenda")').click();
    await expect(page.locator('.agenda-view')).toBeVisible();
    expect(await page.locator('.agenda-day-row').count()).toBeGreaterThan(0);
    await expect(page.locator('.agenda-date-badge').first()).toBeVisible();
  });

  test('switches back to month view', async ({ page }) => {
    await page.locator('.view-switcher button:has-text("Semana")').click();
    await expect(page.locator('.week-grid')).toBeVisible();
    await page.locator('.view-switcher button:has-text("Mes")').click();
    await expect(page.locator('.day-grid')).toBeVisible();
    await expect(
      page.locator('.view-switcher button:has-text("Mes")')
    ).toHaveAttribute('aria-pressed', 'true');
  });
});

test.describe('Calendar — day panel tasks', () => {
  test.beforeEach(async ({ page }) => {
    await stubGoogleConnected(page);
    await page.addInitScript(() => localStorage.setItem('joidy-calendar-view', 'month'));
    await authGoto(page, '/calendar');
    await page.locator('.day-cell.today').click();
    await expect(page.locator('.quick-add')).toBeVisible();
  });

  test('quick-add creates a task on the selected day', async ({ page }) => {
    const title = `E2E Cal QuickAdd ${Date.now()}`;
    await page
      .locator('.quick-add input[aria-label="Nueva tarea… (título + Enter)"]')
      .fill(title);
    await page.locator('.quick-add button[aria-label="Añadir tarea"]').click();
    // Shows up in the day-detail list (the month cell only renders the
    // first 2 items, so assert via the day panel).
    await expect(
      page.locator('.day-detail .event-item .event-summary', { hasText: title })
    ).toBeVisible();
  });

  test('inline edit renames a task', async ({ page }) => {
    const title = `E2E Cal Edit ${Date.now()}`;
    const renamed = `${title} v2`;
    await page
      .locator('.quick-add input[aria-label="Nueva tarea… (título + Enter)"]')
      .fill(title);
    await page.locator('.quick-add button[aria-label="Añadir tarea"]').click();
    const item = page.locator('.day-detail .event-item', { hasText: title });
    await expect(item).toBeVisible();
    await item.locator('button[aria-label="Editar"]').click();
    await page.locator('.edit-form input[aria-label="Título de la tarea"]').fill(renamed);
    await page.locator('.edit-form button[aria-label="Guardar"]').click();
    await expect(
      page.locator('.day-detail .event-item .event-summary', { hasText: renamed })
    ).toBeVisible();
  });

  test('done toggle marks a task as completed', async ({ page }) => {
    const title = `E2E Cal Done ${Date.now()}`;
    await page
      .locator('.quick-add input[aria-label="Nueva tarea… (título + Enter)"]')
      .fill(title);
    await page.locator('.quick-add button[aria-label="Añadir tarea"]').click();
    const item = page.locator('.day-detail .event-item', { hasText: title });
    await expect(item).toBeVisible();
    await item.locator('button[aria-label="Completar tarea"]').click();
    await expect(item).toHaveClass(/done/);
  });

  test('delete removes a task from the day panel', async ({ page }) => {
    const title = `E2E Cal Delete ${Date.now()}`;
    await page
      .locator('.quick-add input[aria-label="Nueva tarea… (título + Enter)"]')
      .fill(title);
    await page.locator('.quick-add button[aria-label="Añadir tarea"]').click();
    const item = page.locator('.day-detail .event-item', { hasText: title });
    await expect(item).toBeVisible();
    await item.locator('button[aria-label="Eliminar"]').click();
    await expect(item).toHaveCount(0);
  });
});

test.describe('Calendar — drag & drop', () => {
  test.beforeEach(async ({ page }) => {
    await stubGoogleConnected(page);
    await page.addInitScript(() => localStorage.setItem('joidy-calendar-view', 'month'));
  });

  test('dragging a task chip to another day reschedules it', async ({ page }) => {
    const title = `E2E Cal Drag ${Date.now()}`;
    // Seed on a future day no other test touches — the month cell only
    // renders the first 2 items, so a busy day could hide the chip.
    const src = new Date();
    src.setDate(src.getDate() + 5);
    await seedTask(page, title, localDayKey(src));
    await authGoto(page, '/calendar');

    const srcCell = page.locator('.day-cell', {
      has: page.locator('.chip', { hasText: title }),
    });
    const chip = srcCell.locator('.chip', { hasText: title });
    await expect(srcCell).toHaveCount(1);
    await expect(chip).toBeVisible();
    // Drop on an empty in-month day cell (no chips of any kind). Pin the
    // element handle now — after the drop the cell holds the chip, so a
    // hasNot-filtered locator would re-resolve to a different cell.
    const target = page
      .locator('.day-cell:not(.out):not(.today)')
      .filter({ hasNot: page.locator('.chip') })
      .first();
    await expect(target).toBeVisible();
    const targetEl = await target.elementHandle();
    if (!targetEl) throw new Error('target cell handle missing');

    // HTML5 DnD: dispatch real drag events with a DataTransfer. `dragend`
    // is skipped — the chip element re-renders at its new cell on drop, and
    // the drop handler already clears the drag state.
    const dataTransfer = await page.evaluateHandle(() => new DataTransfer());
    await chip.dispatchEvent('dragstart', { dataTransfer });
    await targetEl.dispatchEvent('drop', { dataTransfer });

    // The chip now lives in the target cell — and only there.
    await targetEl.waitForSelector(`.chip:has-text("${title}")`, { timeout: 5000 });
    await expect(
      page.locator('.day-cell', { has: page.locator('.chip', { hasText: title }) })
    ).toHaveCount(1);
  });

  test('dragging an unscheduled task from the tray to a day schedules it', async ({
    page,
  }) => {
    const title = `E2E Cal TrayDrag ${Date.now()}`;
    await seedTask(page, title, null);
    await authGoto(page, '/calendar');

    const trayTask = page.locator('.unscheduled-tray .tray-task', { hasText: title });
    await expect(trayTask).toBeVisible();

    const dataTransfer = await page.evaluateHandle(() => new DataTransfer());
    await trayTask.dispatchEvent('dragstart', { dataTransfer });
    await page.locator('.day-cell.today').dispatchEvent('drop', { dataTransfer });

    // Left the tray and now shows in today's day-detail (the month cell only
    // renders the first 2 items, so assert via the day panel).
    await expect(trayTask).toHaveCount(0);
    await page.locator('.day-cell.today').click();
    await expect(
      page.locator('.day-detail .event-item .event-summary', { hasText: title })
    ).toBeVisible();
  });
});

test.describe('Calendar — unscheduled tray', () => {
  test('tray quick-add creates an unscheduled task', async ({ page }) => {
    await stubGoogleConnected(page);
    await authGoto(page, '/calendar');
    const title = `E2E Cal Unscheduled ${Date.now()}`;
    await page.locator('.tray-add-input').fill(title);
    await page.locator('.tray-add button[aria-label="Añadir tarea"]').click();
    await expect(
      page.locator('.unscheduled-tray .tray-task', { hasText: title })
    ).toBeVisible();
  });
});

test.describe('Calendar — AI disabled', () => {
  test('plan suggest reports unavailable without breaking the page', async ({
    page,
  }) => {
    await stubGoogleConnected(page);
    // The "AI disabled" response the API returns when no provider is
    // configured — deterministic regardless of the stack's AI setup.
    await page.route('**/ai/plan-suggest', (route) =>
      route.fulfill({ json: { suggestions: [], available: false, reason: 'disabled' } })
    );
    await authGoto(page, '/calendar');
    await expect(page.locator('.day-grid')).toBeVisible();
    await page.locator('button.plan-btn').click();
    await expect(
      page.locator('.toast', {
        hasText: 'La planificación con IA no está configurada',
      })
    ).toBeVisible({ timeout: 8000 });
    // Page remains fully functional afterwards
    await page.locator('.day-cell.today').click();
    await expect(page.locator('.quick-add')).toBeVisible();
  });
});
