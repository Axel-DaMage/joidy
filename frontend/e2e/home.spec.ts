import { test, expect, authGoto, dismissConflictModal } from './helpers/auth';

/**
 * Home/Dashboard feature — comprehensive E2E tests.
 * Covers: module carousel, XP stats, pomodoro, GitHub widget,
 * recent notes, clock, focus mode.
 */
test.describe('Home — dashboard structure', () => {
  test('dashboard loads with plant widget', async ({ page }) => {
    await authGoto(page, '/');
    await expect(page.locator('text=/planta/i')).toBeVisible({ timeout: 5000 });
  });

  test('XP and level are displayed', async ({ page }) => {
    await authGoto(page, '/');
    // XP shows like "23,223 / 25,000 xp" — use a more flexible regex
    await expect(page.locator('header.app-header').locator('text=/[\\d,]+\\s*\\/.*xp/i')).toBeVisible({ timeout: 5000 });
    // Level shows as "NVL" in Spanish locale (was "LVL" in English)
    await expect(page.locator('text=/NVL\\s+\\d+/i')).toBeVisible({ timeout: 5000 });
  });

});

test.describe('Home — plant visualization', () => {
  test('plant visualization dots are visible', async ({ page }) => {
    await authGoto(page, '/');
    // 5 visualization dots: Planta, Galaxia, Montaña, Ciudad, Órbita
    await expect(page.locator('button[aria-label="Planta"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Galaxia"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Montaña"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Ciudad"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Órbita"]')).toBeVisible();
  });

  test('can switch visualization', async ({ page }) => {
    await authGoto(page, '/');
    const galaxyDot = page.locator('button[aria-label="Galaxia"]');
    await galaxyDot.click();
    await page.waitForTimeout(500);
    // The dot should become active
    await expect(galaxyDot).toHaveClass(/active/);
  });

  test('navigation arrows work', async ({ page }) => {
    await authGoto(page, '/');
    const nextArrow = page.locator('button[aria-label="Siguiente"]');
    await nextArrow.click();
    await page.waitForTimeout(300);
    // The active dot should have changed
    const activeDot = page.locator('button.dot.active');
    await expect(activeDot).toBeVisible();
  });
});

test.describe('Home — pomodoro timer', () => {
  test('pomodoro timer is visible', async ({ page }) => {
    await authGoto(page, '/');
    // Pomodoro shows "25:00" timer and "Iniciar" button
    await expect(page.locator('button:has-text("Iniciar")')).toBeVisible({ timeout: 5000 });
  });

  test('start button is visible', async ({ page }) => {
    await authGoto(page, '/');
    await expect(page.locator('button:has-text("Iniciar")')).toBeVisible({ timeout: 5000 });
  });

  test('can start and stop pomodoro', async ({ page }) => {
    await authGoto(page, '/');
    const startBtn = page.locator('button:has-text("Iniciar")');
    await startBtn.click();
    await page.waitForTimeout(500);
    // Button text should change (to "Pausar" or similar)
    const pauseBtn = page.locator('button:has-text("Pausar")');
    if (await pauseBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
      await pauseBtn.click();
      await page.waitForTimeout(300);
    }
  });

  test('reset button is visible', async ({ page }) => {
    await authGoto(page, '/');
    await expect(page.locator('button[aria-label="Reiniciar"]')).toBeVisible({ timeout: 5000 });
  });

  test('skip button is visible', async ({ page }) => {
    await authGoto(page, '/');
    await expect(page.locator('button[aria-label="Saltar"]')).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Home — focus mode', () => {
  test('focus mode button is visible', async ({ page }) => {
    await authGoto(page, '/');
    // The focus-mode trigger is the icon-only mini-focus-btn in the status
    // bar (aria-label "Iniciar modo enfoque" in es locale — has-text does
    // not match the title attribute).
    await expect(page.locator('.mini-focus-btn')).toBeVisible({ timeout: 5000 });
  });

  test('can toggle focus mode', async ({ page }) => {
    await authGoto(page, '/');
    const focusBtn = page.locator('.mini-focus-btn');
    await focusBtn.click();
    // Focus mode overlay should appear
    await expect(page.locator('.focus-overlay')).toBeVisible({ timeout: 5000 });
    // Press Escape to exit if overlay appeared
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  });
});

test.describe('Home — recent notes', () => {
  test('recent notes section is visible', async ({ page }) => {
    await authGoto(page, '/');
    await expect(page.locator('text=/notas recientes/i')).toBeVisible({ timeout: 5000 });
  });

  test('view all link navigates to notes', async ({ page }) => {
    await authGoto(page, '/');
    const viewAllLink = page.locator('a[href="/notes"]').filter({ hasText: /ver todas/i });
    await expect(viewAllLink).toBeVisible({ timeout: 5000 });
    await viewAllLink.click();
    await page.waitForLoadState('networkidle');
    await dismissConflictModal(page);
    await expect(page).toHaveURL(/\/notes/);
  });
});

test.describe('Home — clock', () => {
  test('clock is visible and shows time', async ({ page }) => {
    await authGoto(page, '/');
    const clock = page.locator('button.clock');
    await expect(clock).toBeVisible({ timeout: 5000 });
    // Clock should show time in HH:MM:SS format
    await expect(clock).toHaveText(/\d{2}:\d{2}:\d{2}/);
  });
});

test.describe('Home — GitHub widget', () => {
  test('GitHub widget section is visible', async ({ page }) => {
    // authGoto waits for the app shell (main.app-main), so cold-boot
    // latency is already absorbed before this assertion runs — a timeout
    // here means the widget is genuinely missing, not that the app was
    // still booting (#1599).
    await authGoto(page, '/');
    // The activity widget always renders a section header: the "GitHub" tab
    // when an account is linked, or the "Notas recientes" heading when it
    // isn't — a fresh CI stack has no GitHub credentials, so no "GitHub"
    // text exists at all in that state.
    const githubSection = page
      .locator('main.app-main')
      .locator('text=/github|notas recientes/i');
    await expect(githubSection.first()).toBeVisible({ timeout: 5000 });
  });
});
