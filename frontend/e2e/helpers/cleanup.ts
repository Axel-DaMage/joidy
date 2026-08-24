/**
 * Global teardown for E2E tests — cleans up test data left in the database (#565).
 *
 * This runs after all Playwright tests complete. It deletes any notes, goals,
 * and personal streaks whose names match known E2E test patterns. This prevents
 * test artifacts from accumulating in the dev database across multiple test runs.
 *
 * The cleanup uses the API directly (with JWT auth) rather than UI interactions,
 * so it's fast and doesn't depend on the frontend being in a specific state.
 */

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';
const TEST_PASSWORD = process.env.JOIDY_TEST_PASSWORD ?? 'root';

/**
 * Known E2E test data name patterns. Any note/goal/streak whose title/name
 * matches one of these patterns (case-insensitive) will be deleted.
 */
const E2E_PATTERNS = [
  'E2E',
  'Test Goal',
  'Test Title from E2E',
  'Goal Title from E2E',
  'Updated E2E Note',
  'E2E API Test Note',
  'Test Audit Goal',
  '33 E2E',
  'Streak A',
  'Streak B',
  'Freeze Streak',
  'Drink Water', // Created by streak tests
  'Pag Test',
  'Pag Streak',
  'Graph Pag Test',
];

async function getAuthToken(): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'user', password: TEST_PASSWORD }),
  });
  if (!res.ok) {
    console.error(`[cleanup] Login failed: ${res.status}`);
    return '';
  }
  const data = await res.json();
  return data.access_token;
}

function matchesPattern(name: string): boolean {
  const lower = name.toLowerCase();
  return E2E_PATTERNS.some((p) => lower.includes(p.toLowerCase()));
}

async function cleanupNotes(token: string): Promise<number> {
  let deleted = 0;
  try {
    const res = await fetch(`${API_BASE}/notes/?limit=1000`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return 0;
    const notes = await res.json();
    for (const note of notes) {
      if (matchesPattern(note.title || '')) {
        const delRes = await fetch(`${API_BASE}/notes/${note.id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (delRes.ok) deleted++;
      }
    }
  } catch (e) {
    console.error('[cleanup] Notes cleanup error:', e);
  }
  return deleted;
}

async function cleanupGoals(token: string): Promise<number> {
  let deleted = 0;
  try {
    const res = await fetch(`${API_BASE}/goals/?limit=200`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return 0;
    const goals = await res.json();
    for (const goal of goals) {
      if (matchesPattern(goal.title || '')) {
        const delRes = await fetch(`${API_BASE}/goals/${goal.id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (delRes.ok) deleted++;
      }
    }
  } catch (e) {
    console.error('[cleanup] Goals cleanup error:', e);
  }
  return deleted;
}

async function cleanupStreaks(token: string): Promise<number> {
  let deleted = 0;
  try {
    const res = await fetch(`${API_BASE}/personal-streaks/?include_archived=true&limit=200`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return 0;
    const streaks = await res.json();
    for (const streak of streaks) {
      if (matchesPattern(streak.name || '')) {
        const delRes = await fetch(`${API_BASE}/personal-streaks/${streak.id}`, {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        });
        if (delRes.ok) deleted++;
      }
    }
  } catch (e) {
    console.error('[cleanup] Streaks cleanup error:', e);
  }
  return deleted;
}

export default async function globalTeardown() {
  console.log('[cleanup] Starting E2E test data cleanup (#565)...');
  const token = await getAuthToken();
  if (!token) {
    console.warn('[cleanup] No auth token — skipping cleanup');
    return;
  }

  const notesDeleted = await cleanupNotes(token);
  const goalsDeleted = await cleanupGoals(token);
  const streaksDeleted = await cleanupStreaks(token);

  console.log(
    `[cleanup] Done: ${notesDeleted} notes, ${goalsDeleted} goals, ${streaksDeleted} streaks deleted.`
  );
}
