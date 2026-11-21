/**
 * Global setup for E2E tests — seeds the minimum dataset the specs need (#1476).
 *
 * Every CI shard boots a fresh stack with an empty database, but several
 * specs assume pre-existing entities: note cards (notes/note-editor),
 * goal cards (goals/goal-editor), streak items (streaks/streak-interactions),
 * recent notes (home) and graph nodes/tags/links (graph). This setup logs
 * in via /auth/login and creates them through the REST API — fast and
 * independent of frontend state, exactly like helpers/cleanup.ts.
 *
 * Safety:
 *  - Every seeded title/name contains a substring from E2E_PATTERNS in
 *    cleanup.ts, so the global teardown deletes them after the run.
 *  - Seeding is idempotent: entities whose title/name already exists are
 *    skipped, so re-running `npx playwright test` on a dev database does
 *    not pile up duplicates between teardowns.
 */

const API_BASE = process.env.PLAYWRIGHT_API_URL ?? 'http://localhost:8000';
const TEST_PASSWORD = process.env.JOIDY_TEST_PASSWORD ?? 'root';

/**
 * Seed definitions. Titles/names MUST keep matching E2E_PATTERNS in
 * cleanup.ts ('E2E', 'Drink Water', …) or they will leak after teardown.
 */
const SEED_NOTES = [
  {
    // notes.spec.ts searches 'Track Aws' and expects a match.
    title: 'Track Aws E2E',
    content: 'Nota sembrada para la suite E2E. Cubre la búsqueda de notas.',
    tags: ['e2e-seed', 'aws'],
  },
  {
    // The wikilink resolves against the note above → a graph edge, and the
    // tags give the graph tag nodes/co-occurrence data (graph.spec.ts).
    title: 'E2E Seed Graph Note',
    content: 'Relacionada con [[Track Aws E2E]] para generar un link del grafo.',
    tags: ['e2e-seed', 'graph'],
  },
  {
    title: 'E2E Seed Journal Note',
    content: 'Contenido de relleno para listados, editor y notas recientes.',
    tags: ['e2e-seed'],
  },
];

const SEED_GOALS = [
  {
    // 'G1' is the search term used by goals.spec.ts; the description feeds
    // the word/char stats shown in the goal editor toolbar.
    title: 'E2E G1 Seed Goal',
    description:
      'Objetivo sembrado para la suite E2E con suficiente texto para las estadísticas del editor.',
    temporality: 'DAILY',
  },
  {
    title: 'E2E Second Goal',
    description: 'Segundo objetivo sembrado para navegación y filtros E2E.',
    temporality: 'WEEKLY',
  },
];

const SEED_STREAKS = [
  {
    // streaks.spec.ts filters by 'Drink' and expects this exact name.
    name: 'Drink Water',
    emoji: '💧',
    description: 'Racha sembrada para E2E.',
  },
  {
    name: 'E2E Morning Pages',
    emoji: '☀️',
    description: 'Racha sembrada para E2E.',
  },
  {
    name: 'E2E Reading Habit',
    emoji: '📚',
    description: 'Racha sembrada para E2E.',
  },
];

async function getAuthToken(): Promise<string> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: 'user', password: TEST_PASSWORD }),
  });
  if (!res.ok) {
    console.error(`[seed] Login failed: ${res.status}`);
    return '';
  }
  const data = await res.json();
  return data.access_token;
}

function authHeaders(token: string) {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

async function seedNotes(token: string): Promise<number> {
  let created = 0;
  try {
    const res = await fetch(`${API_BASE}/notes/?limit=1000`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      console.error(`[seed] Could not list notes: ${res.status}`);
      return 0;
    }
    const existing = new Set(
      (await res.json()).map((n: { title?: string }) => (n.title || '').toLowerCase())
    );
    for (const note of SEED_NOTES) {
      if (existing.has(note.title.toLowerCase())) continue;
      const createRes = await fetch(`${API_BASE}/notes/`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(note),
      });
      if (createRes.ok) {
        created++;
      } else {
        console.error(`[seed] Note "${note.title}" failed: ${createRes.status}`);
      }
    }
  } catch (e) {
    console.error('[seed] Notes seeding error:', e);
  }
  return created;
}

async function seedGoals(token: string): Promise<number> {
  let created = 0;
  try {
    const res = await fetch(`${API_BASE}/goals/?limit=200`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      console.error(`[seed] Could not list goals: ${res.status}`);
      return 0;
    }
    const existing = new Set(
      (await res.json()).map((g: { title?: string }) => (g.title || '').toLowerCase())
    );
    for (const goal of SEED_GOALS) {
      if (existing.has(goal.title.toLowerCase())) continue;
      const createRes = await fetch(`${API_BASE}/goals/`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(goal),
      });
      if (createRes.ok) {
        created++;
      } else {
        console.error(`[seed] Goal "${goal.title}" failed: ${createRes.status}`);
      }
    }
  } catch (e) {
    console.error('[seed] Goals seeding error:', e);
  }
  return created;
}

async function seedStreaks(token: string): Promise<number> {
  let created = 0;
  try {
    const res = await fetch(`${API_BASE}/personal-streaks/?include_archived=true&limit=200`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      console.error(`[seed] Could not list streaks: ${res.status}`);
      return 0;
    }
    const existing = new Set(
      (await res.json()).map((s: { name?: string }) => (s.name || '').toLowerCase())
    );
    for (const streak of SEED_STREAKS) {
      if (existing.has(streak.name.toLowerCase())) continue;
      const createRes = await fetch(`${API_BASE}/personal-streaks/`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify(streak),
      });
      if (createRes.ok) {
        created++;
      } else {
        console.error(`[seed] Streak "${streak.name}" failed: ${createRes.status}`);
      }
    }
  } catch (e) {
    console.error('[seed] Streaks seeding error:', e);
  }
  return created;
}

export default async function globalSetup() {
  console.log('[seed] Seeding E2E test data (#1476)...');
  const token = await getAuthToken();
  if (!token) {
    console.warn('[seed] No auth token — skipping seed');
    return;
  }

  const notesCreated = await seedNotes(token);
  const goalsCreated = await seedGoals(token);
  const streaksCreated = await seedStreaks(token);

  console.log(
    `[seed] Done: ${notesCreated} notes, ${goalsCreated} goals, ${streaksCreated} streaks created ` +
      `(existing entities with the same title/name were skipped).`
  );
}
