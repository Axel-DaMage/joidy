import { test as base, expect, type Page } from '@playwright/test';

/**
 * Auth helper for E2E tests.
 *
 * Joidy uses a single-user JWT auth. The token is stored in localStorage
 * under the `joidy_session` key. This helper logs in via the API and
 * injects the session before the page loads, so tests start authenticated.
 */

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';
const TEST_PASSWORD = process.env.JOIDY_TEST_PASSWORD ?? 'root';

export interface AuthSession {
  token: string;
  username: string;
}

/**
 * Log in via the API and return the session object.
 * Caches the token for the lifetime of the process.
 */
let cachedToken: string | null = null;

export async function getAuthToken(): Promise<string> {
  if (cachedToken) return cachedToken;
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'user', password: TEST_PASSWORD }),
  });
  if (!res.ok) {
    throw new Error(`Login failed: ${res.status} ${await res.text()}`);
  }
  const data = await res.json();
  cachedToken = data.access_token;
  return cachedToken!;
}

/**
 * Inject the auth session into localStorage before the page navigates.
 * Must be called before `page.goto()`.
 */
export async function authenticate(page: Page): Promise<void> {
  const token = await getAuthToken();
  await page.addInitScript(([token]) => {
    // Auth session — must match UserSession interface in session.ts
    // Missing required fields (id, preferences, createdAt) cause the store
    // to treat the session as invalid, leading to 401s and auto-logout.
    localStorage.setItem(
      'joidy_session',
      JSON.stringify({
        id: '1',
        username: 'user',
        token,
        preferences: {
          theme: 'dark',
          timezone: 'Europe/Madrid',
          language: 'es',
        },
        createdAt: new Date().toISOString(),
      })
    );
    // Enable Dev Mode — pages under development show "En Construcción"
    // unless dev mode is ON (stored in localStorage key 'joidy-dev-mode')
    localStorage.setItem('joidy-dev-mode', 'true');
    // Skip the onboarding tour — its spotlight overlay intercepts pointer
    // events and makes every nav click time out on a fresh database.
    localStorage.setItem('joidy-onboarding-complete', 'true');
    // Set locale to Spanish — the app detects browser language which may
    // be English in headless Chrome. Stored in 'joidy:locale' key.
    localStorage.setItem('joidy:locale', 'es-ES');
  }, [token]);
}

/**
 * Dismiss any sync conflict modal that may appear on page load.
 * Conflicts can appear if the vault watcher detected changes — tests
 * should call this after navigation to ensure a clean state.
 */
export async function dismissConflictModal(page: Page): Promise<void> {
  const modal = page.locator('.modal-overlay[aria-label="Conflicto de Sincronización"]');
  if (await modal.isVisible({ timeout: 1000 }).catch(() => false)) {
    // Click "Saltar" (Skip) to dismiss without resolving
    const skipBtn = modal.locator('button:has-text("Saltar")');
    if (await skipBtn.isVisible().catch(() => false)) {
      await skipBtn.click();
    } else {
      // Fallback: click the close button
      const closeBtn = modal.locator('button[aria-label="Cerrar"]');
      if (await closeBtn.isVisible().catch(() => false)) {
        await closeBtn.click();
      }
    }
    await modal.waitFor({ state: 'hidden', timeout: 2000 }).catch(() => {});
  }
}

/**
 * Navigate to a page with auth pre-injected and conflict modal dismissed.
 */
export async function authGoto(page: Page, path: string): Promise<void> {
  await page.goto(path);
  // Wait for DOM to be ready. No networkidle: the app keeps a WebSocket
  // open (/ws notifications), so networkidle never resolves and this call
  // would burn its full timeout on EVERY navigation (~165 per suite).
  await page.waitForLoadState('domcontentloaded');
  // Wait for the app shell: the layout renders a `.boot-screen`
  // ("Cargando Joidy…") until the setup-status request resolves, and on
  // cold boot that latency can exceed the per-spec locator timeouts,
  // flaking tests like the GitHub widget check (#1599). Absorbing boot
  // time here keeps each spec's timeout scoped to the element under test;
  // a failure waiting on this locator means the app never booted, which
  // stays distinguishable in the output from a missing widget. The
  // assertion-level locators that follow carry their own auto-wait.
  await page.locator('main.app-main').waitFor({ state: 'visible', timeout: 30_000 });
  // Short settle for the async sync-conflict modal check below — the
  // modal only exists when the API reports a conflict (never in CI), but
  // on dev databases it can mount a tick after the shell.
  await page.waitForTimeout(250);
  await dismissConflictModal(page);
}

/**
 * Extended test fixture that auto-authenticates before each test.
 */
export const test = base.extend({
  // eslint-disable-next-line no-empty-pattern
  page: async ({ page }, use) => {
    await authenticate(page);
    await use(page);
  },
});

export { expect };
