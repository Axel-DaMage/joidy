<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { dev } from '$app/environment';
  import { fly } from 'svelte/transition';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import Plant          from '$lib/components/Plant.svelte';
  import GalaxyModule   from '$lib/components/GalaxyModule.svelte';
  import MountainModule from '$lib/components/MountainModule.svelte';
  import CityModule     from '$lib/components/CityModule.svelte';
  import OrbitModule    from '$lib/components/OrbitModule.svelte';
  import XPBar          from '$lib/components/XPBar.svelte';
  import NoteCard       from '$lib/components/NoteCard.svelte';
  import PomodoroWidget from '$lib/components/PomodoroWidget.svelte';
  import { Target } from 'lucide-svelte';
  import { startFocusMode } from '$lib/stores/focusMode';
  import TimeWidget from '$lib/components/TimeWidget.svelte';
  import WeatherWidget from '$lib/components/WeatherWidget.svelte';
  import Widget         from '$lib/components/Widget.svelte';
  import GithubWidget from '$lib/components/GithubWidget.svelte';
  import { totalXP, currentStreak, lastActivity, nextStageXP, globalLevel } from '$lib/stores/gamification';
  import { openShare } from '$lib/stores/shareAchievement';
  import { Share2 } from 'lucide-svelte';
  import ActivityProgress from '$lib/components/ActivityProgress.svelte';
  import { notes, loadNotes, notesLoadedOnce } from '$lib/stores/notes';
  import { dashboardLayout } from '$lib/stores/layout';
  import { accentColors } from '$lib/stores/settings';
  import { api } from '$lib/api';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { captureSnapshot, getSnapshot } from '$lib/stores/pageSnapshots';
  import { routeCache } from '$lib/stores/routeCache';
  import { logger } from '$lib/utils/logger';

  // ── Module carousel ────────────────────────────────────────────────────────
  const MODULES = [
    { id: 'planta',  label: 'Planta'  },
    { id: 'galaxia', label: 'Galaxia' },
    { id: 'montana', label: 'Montaña' },
    { id: 'ciudad',  label: 'Ciudad'  },
    { id: 'orbita',  label: 'Órbita'  },
  ];

  let moduleIdx = 0;
  let slideDir  = 1;
  let modulePrefsReady = false;

  function prevModule() { slideDir = -1; moduleIdx = (moduleIdx - 1 + MODULES.length) % MODULES.length; }
  function nextModule() { slideDir =  1; moduleIdx = (moduleIdx + 1) % MODULES.length; }

  // ── Data ───────────────────────────────────────────────────────────────────
  let githubConnected = false;
  let githubLoading = false;
  let githubIssues: { id: number; number: number; title: string; repo: string; url: string }[] = [];
  let githubPRs: { id: number; number: number; title: string; repo: string; url: string }[] = [];
  let repoColors: Record<string, string> = {};
  let issueStats = { open: 0, total: 0 };
  let prStats = { open: 0, total: 0 };
  let ghFilter = 'created';
  let ghType = 'all';
  const GH_ITEM_LIMIT = 9;
  const GH_CACHE_KEY = 'joidy_github_cache_v1';
  const GH_CACHE_TTL_MS = 1000 * 60 * 10;

  type GithubCache = {
    connected: boolean;
    filter: string;
    type: string;
    issues: { id: number; number: number; title: string; repo: string; url: string }[];
    prs: { id: number; number: number; title: string; repo: string; url: string }[];
    issueStats: { open: number; total: number };
    prStats: { open: number; total: number };
    repoColors: Record<string, string>;
    ts: number;
  };

  function readGithubCache(): GithubCache | null {
    try {
      if (typeof localStorage === 'undefined') return null;
      const raw = localStorage.getItem(GH_CACHE_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw) as GithubCache;
      if (!parsed || typeof parsed !== 'object') return null;
      if (!isGithubCacheFresh(parsed)) {
        localStorage.removeItem(GH_CACHE_KEY);
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }

  function writeGithubCache(cache: GithubCache) {
    try {
      if (typeof localStorage === 'undefined') return;
      localStorage.setItem(GH_CACHE_KEY, JSON.stringify(cache));
    } catch {
      // Ignore cache write failures (private mode, quota, etc.)
    }
  }

  function applyGithubCache(cache: GithubCache) {
    githubConnected = cache.connected;
    ghFilter = cache.filter || ghFilter;
    ghType = cache.type || ghType;
    githubIssues = Array.isArray(cache.issues) ? cache.issues : [];
    githubPRs = Array.isArray(cache.prs) ? cache.prs : [];
    issueStats = cache.issueStats || { open: 0, total: 0 };
    prStats = cache.prStats || { open: 0, total: 0 };
    repoColors = cache.repoColors || {};
  }

  function isGithubCacheFresh(cache: GithubCache) {
    return Date.now() - cache.ts < GH_CACHE_TTL_MS;
  }

  function clearGithubCache() {
    try {
      if (typeof localStorage === 'undefined') return;
      localStorage.removeItem(GH_CACHE_KEY);
    } catch {
      // Ignore clear failures
    }
  }

  async function loadGitHubData(filter: string = 'created') {
    if (!githubConnected) return;
    githubLoading = true;
    try {
      const [issuesRes, pullsRes] = await Promise.all([
        api.github.issues(filter),
        api.github.pulls(filter)
      ]);
      githubIssues = (issuesRes.issues || []).slice(0, GH_ITEM_LIMIT);
      issueStats = issuesRes.stats || { open: 0, total: 0 };
      githubPRs = (pullsRes.pulls || []).slice(0, GH_ITEM_LIMIT);
      prStats = pullsRes.stats || { open: 0, total: 0 };
      writeGithubCache({
        connected: githubConnected,
        filter,
        type: ghType,
        issues: githubIssues,
        prs: githubPRs,
        issueStats,
        prStats,
        repoColors,
        ts: Date.now()
      });
    } catch (e) { 
      logger.error('GitHub error:', e); 
      githubIssues = [];
      githubPRs = [];
    } finally {
      githubLoading = false;
    }
  }

  function setGhFilter(f: string) {
    ghFilter = f;
    loadGitHubData(f);
  }

  function setGhType(t: string) {
    ghType = t;
  }

  $: isWilted = (() => {
    if (!$lastActivity) return false;
    const last = new Date($lastActivity);
    if (isNaN(last.getTime())) return false;
    return (Date.now() - last.getTime()) / 86400000 > 2;
  })();

  let githubStatusChecked = false;
  let ttiMeasured = false;

  $: recentNotes = $notes.slice(0, 5);

  onMount(() => {
    if (typeof performance !== 'undefined') {
      performance.mark('dashboard-mount');
    }
    const cached = readGithubCache();
    if (cached) {
      applyGithubCache(cached);
    }

    const snap = getSnapshot('/');
    if (snap) {
      moduleIdx = snap.state.moduleIdx ?? 0;
      slideDir = snap.state.slideDir ?? 1;
    }

    const savedNotesUi = loadUserSettings().notesUi;
    if (savedNotesUi?.panelWidth !== undefined) {
      panelWidth = Number(savedNotesUi.panelWidth);
    }
    modulePrefsReady = true;

    if (!$notesLoadedOnce) {
      loadNotes();
    }
    
    requestAnimationFrame(async () => {
      try {
        const status = await api.github.status();
        githubConnected = status.connected;
        if (githubConnected) {
          const [reposRes] = await Promise.all([
            api.github.repos(),
            (!cached || !isGithubCacheFresh(cached)) ? loadGitHubData(ghFilter) : Promise.resolve()
          ]);
          repoColors = Object.fromEntries((reposRes.repos || []).map((r: any) => [r.full_name, r.color || '#6366F1']));
          writeGithubCache({
            connected: githubConnected,
            filter: ghFilter,
            type: ghType,
            issues: githubIssues,
            prs: githubPRs,
            issueStats,
            prStats,
            repoColors,
            ts: Date.now()
          });
        } else {
          clearGithubCache();
        }
      } catch (e) { logger.error('GitHub error:', e); }
      finally { githubStatusChecked = true; }
    });

    window.addEventListener('beforeunload', handleBeforeUnload);
  });

  function handleBeforeUnload() {
    const scrollEls = document.querySelectorAll('[id^="panel-"]');
    captureSnapshot('/', { moduleIdx, slideDir }, 
      Array.from(scrollEls).map(el => ({ id: el.id, scrollTop: (el as HTMLElement).scrollTop }))
    );
  }

  $: if (modulePrefsReady && MODULES[moduleIdx]) {
    patchUserSettings({
      dashboard: {
        moduleId: MODULES[moduleIdx].id,
      }
    });
  }

  $: if (!ttiMeasured && githubStatusChecked && $notesLoadedOnce) {
    ttiMeasured = true;
    if (typeof performance !== 'undefined') {
      performance.mark('dashboard-interactive');
      performance.measure('dashboard-tti', 'dashboard-mount', 'dashboard-interactive');
      const entry = performance.getEntriesByName('dashboard-tti').slice(-1)[0];
      if (entry) {
        try {
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('joidy_dashboard_tti_ms', Math.round(entry.duration).toString());
          }
        } catch {
          // Ignore storage failures
        }
        if (dev) {
          logger.info(`Dashboard TTI: ${Math.round(entry.duration)}ms`);
        }
      }
    }
  }

  // Widget renderers per panel
  function leftWidgets(layout: typeof $dashboardLayout) { return layout.left; }
  function rightWidgets(layout: typeof $dashboardLayout) { return layout.right; }

  // Resizable panel synced with notes
  let panelWidth = 260;

  // Level milestones that warrant a shareable achievement card.
  const LEVEL_MILESTONES = [10, 25, 50, 75, 100];
  $: isLevelMilestone = LEVEL_MILESTONES.includes($globalLevel);

  function shareLevel() {
    openShare({
      title: 'Nivel alcanzado',
      icon: 'TrendingUp',
      value: `NVL ${$globalLevel}`,
      subtitle: `${$totalXP.toLocaleString()} XP`,
      color: 'var(--xp)',
    });
  }
</script>

<div class="dashboard" style="--panel-w: {panelWidth}px">

  <!-- ── Left panel ─────────────────────────────────────────────────────────── -->
  <section class="plant-section">

    {#each $dashboardLayout.left as wid, i (wid)}
      <Widget id={wid}>

        {#if wid === 'plant-carousel'}
          <div class="widget-centered">
            <!-- Module navigation -->
            <div class="module-nav">
              <button class="nav-arrow" onclick={prevModule} title="Anterior" aria-label="Anterior"><DynamicIcon name="ChevronLeft" size={14}/></button>
              <span class="module-label mono">{MODULES[moduleIdx].label.toUpperCase()}</span>
              <button class="nav-arrow" onclick={nextModule} title="Siguiente" aria-label="Siguiente"><DynamicIcon name="ChevronRight" size={14}/></button>
            </div>

            <!-- Module viewport -->
            <div class="module-viewport">
              {#key moduleIdx}
                <div class="module-slide" in:fly={{ x: slideDir * 40, duration: 220, opacity: 0 }}>
                  {#if MODULES[moduleIdx].id === 'planta'}
                    <Plant size={160} wilted={isWilted} />
                  {:else if MODULES[moduleIdx].id === 'galaxia'}
                    <GalaxyModule size={160} />
                  {:else if MODULES[moduleIdx].id === 'montana'}
                    <MountainModule size={160} />
                  {:else if MODULES[moduleIdx].id === 'ciudad'}
                    <CityModule size={160} />
                  {:else if MODULES[moduleIdx].id === 'orbita'}
                    <OrbitModule size={160} />
                  {/if}
                </div>
              {/key}
            </div>

            <!-- Dots -->
            <div class="module-dots">
              {#each MODULES as _, idx}
                <button
                  class="dot" class:active={idx === moduleIdx}
                  onclick={() => { slideDir = idx > moduleIdx ? 1 : -1; moduleIdx = idx; }}
                  aria-label={MODULES[idx].label}
                ></button>
              {/each}
            </div>


          </div>

        {:else if wid === 'stats-xp'}
          <div class="widget-centered">
            <div class="stats-row">
              <div class="stat">
                <span class="stat-value mono">{$currentStreak}</span>
                <span class="stat-label label">días</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat">
                {#if $nextStageXP}
                  <span class="stat-value mono">{$totalXP.toLocaleString()}</span>
                  <span class="stat-label label">xp</span>
                {:else}
<span class="stat-value mono" style="color: var(--text-primary);">MAX</span>
                  <span class="stat-label label">xp</span>
                {/if}
              </div>
              <div class="stat-divider"></div>
              <div class="stat">
                <span class="stat-value mono">{$notes.length}</span>
                <span class="stat-label label">notas</span>
              </div>
            </div>
            {#if isLevelMilestone}
              <button
                class="level-share-btn"
                onclick={shareLevel}
                title="Compartir nivel"
                aria-label="Compartir nivel {$globalLevel}"
              >
                <Share2 size={11} />
                <span>Compartir nivel</span>
              </button>
            {/if}
          </div>

        {:else if wid === 'activity-progress'}
          <ActivityProgress />

        {:else if wid === 'time-widget'}
          <TimeWidget />

        {:else if wid === 'weather-widget'}
          <WeatherWidget />

        {:else if wid === 'pomodoro'}
          <PomodoroWidget />
          <button class="focus-mode-btn" onclick={() => startFocusMode()} aria-label="Iniciar modo enfoque">
            <Target size={16} />
            Modo Enfoque
          </button>

        {:else if wid === 'recent-notes'}
          <div class="section-header">
            <h4 style="color: {$accentColors[0]}">Notas recientes</h4>
            <a href="/notes" class="btn btn-ghost" style="font-size:11px; padding:2px 8px;">ver todas →</a>
          </div>
          <div class="recent-notes">
            {#if recentNotes.length === 0}
              <div class="empty-state"><span class="caption">No hay notas aún.</span></div>
            {:else}
              {#each recentNotes as note}
                <NoteCard {note} showTags={false} on:select={() => goto(`/notes?id=${note.id}`)} />
              {/each}
            {/if}
          </div>

        {:else if wid === 'github-issues'}
          <GithubWidget
            accentColor={$accentColors[1]}
            {githubConnected}
            {githubLoading}
            {githubIssues}
            {githubPRs}
            {repoColors}
            {issueStats}
            {prStats}
            {ghFilter}
            {ghType}
            itemLimit={GH_ITEM_LIMIT}
            onSetFilter={setGhFilter}
            onSetType={setGhType}
          />
        {/if}

      </Widget>
    {/each}

  </section>

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <div class="resize-handle static"></div>

  <!-- ── Right panel ────────────────────────────────────────────────────────── -->
  <section class="activity-section">

    {#each $dashboardLayout.right as wid, i (wid)}
      <Widget id={wid}>

        {#if wid === 'recent-notes'}
          <div class="section-header">
            <h4 style="color: {$accentColors[0]}">Notas recientes</h4>
            <a href="/notes" class="btn btn-ghost" style="font-size:11px; padding:2px 8px;">ver todas →</a>
          </div>
          <div class="recent-notes">
            {#if recentNotes.length === 0}
              <div class="empty-state"><span class="caption">No hay notas aún.</span></div>
            {:else}
              {#each recentNotes as note}
                <NoteCard {note} showTags={false} on:select={() => goto(`/notes?id=${note.id}`)} />
              {/each}
            {/if}
          </div>
          <hr class="section-divider" />

        {:else if wid === 'github-issues'}
          <GithubWidget
            accentColor={$accentColors[1]}
            {githubConnected}
            {githubLoading}
            {githubIssues}
            {githubPRs}
            {repoColors}
            {issueStats}
            {prStats}
            {ghFilter}
            {ghType}
            itemLimit={GH_ITEM_LIMIT}
            onSetFilter={setGhFilter}
            onSetType={setGhType}
          />

        {:else if wid === 'plant-carousel'}
          <div class="widget-centered">
            <div class="module-nav">
              <button class="nav-arrow" onclick={prevModule} aria-label="Anterior"><DynamicIcon name="ChevronLeft" size={14}/></button>
              <span class="module-label mono">{MODULES[moduleIdx].label.toUpperCase()}</span>
              <button class="nav-arrow" onclick={nextModule} aria-label="Siguiente"><DynamicIcon name="ChevronRight" size={14}/></button>
            </div>
            <div class="module-viewport">
              {#key moduleIdx}
                <div class="module-slide" in:fly={{ x: slideDir * 40, duration: 220, opacity: 0 }}>
                  {#if MODULES[moduleIdx].id === 'planta'}<Plant size={160} wilted={isWilted} />
                  {:else if MODULES[moduleIdx].id === 'galaxia'}<GalaxyModule size={160} />
                  {:else if MODULES[moduleIdx].id === 'montana'}<MountainModule size={160} />
                  {:else if MODULES[moduleIdx].id === 'ciudad'}<CityModule size={160} />
                  {:else if MODULES[moduleIdx].id === 'orbita'}<OrbitModule size={160} />
                  {/if}
                </div>
              {/key}
            </div>
          </div>

        {:else if wid === 'stats-xp'}
          <div class="widget-centered">
            <div class="stats-row">
              <div class="stat"><span class="stat-value mono">{$currentStreak}</span><span class="stat-label label">días</span></div>
              <div class="stat-divider"></div>
              <div class="stat">{#if $nextStageXP}<span class="stat-value mono">{$totalXP.toLocaleString()}</span><span class="stat-label label">xp</span>{:else}<span class="stat-value mono" style="color: var(--text-primary);">MAX</span><span class="stat-label label">xp</span>{/if}</div>
              <div class="stat-divider"></div>
              <div class="stat"><span class="stat-value mono">{$notes.length}</span><span class="stat-label label">notas</span></div>
            </div>
            {#if isLevelMilestone}
              <button
                class="level-share-btn"
                onclick={shareLevel}
                title="Compartir nivel"
                aria-label="Compartir nivel {$globalLevel}"
              >
                <Share2 size={11} />
                <span>Compartir nivel</span>
              </button>
            {/if}
          </div>

        {:else if wid === 'time-widget'}
          <TimeWidget />

        {:else if wid === 'pomodoro'}
          <PomodoroWidget />
          <button class="focus-mode-btn" onclick={() => startFocusMode()} aria-label="Iniciar modo enfoque">
            <Target size={16} />
            Modo Enfoque
          </button>

        {:else if wid === 'activity-progress'}
          <ActivityProgress />
        {/if}

      </Widget>
    {/each}

  </section>

</div>

<style>
  /* ── Layout — identical to original ── */
  .dashboard {
    display: grid;
    grid-template-columns: var(--panel-w) 5px 1fr;
    height: 100%;
    position: relative;
  }

  /* ── Left panel — identical to original ── */
  .plant-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--s4) var(--s5) var(--s4);
    gap: 10px;
    overflow: hidden;
    background: var(--bg);
  }

  /* ── Module navigation ── */
  .module-nav {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    justify-content: center;
  }

  .module-label {
    font-size: 10px;
    color: var(--text-muted);
    letter-spacing: 0.1em;
    min-width: 80px;
    text-align: center;
  }

  .nav-arrow {
    display: flex; align-items: center; justify-content: center;
    width: 24px; height: 24px;
    background: transparent; border: 1px solid var(--border); border-radius: var(--r);
    color: var(--text-muted); cursor: pointer; transition: all var(--t-fast); flex-shrink: 0;
  }
  .nav-arrow:hover  { border-color: var(--text-muted); color: var(--text-secondary); }
  .nav-arrow:active { transform: scale(0.93); }

  .module-viewport {
    width: 170px; height: 170px;
    position: relative; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
  }

  .module-slide {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
  }

  .module-dots { display: flex; gap: 6px; align-items: center; }

  .dot {
    width: 5px; height: 5px; border-radius: 50%;
    background: var(--border); border: none; padding: 0;
    cursor: pointer; transition: all var(--t-fast);
  }
  .dot.active { background: var(--text-muted); width: 14px; border-radius: 3px; }

  .wilt-notice {
    padding: var(--s2) var(--s3);
    border: 1px solid var(--border); border-radius: var(--r); text-align: center;
  }

  .widget-centered {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 10px 0;
  }

  .xp-section { width: 100%; max-width: 240px; }

  .stats-row {
    display: flex; align-items: center; gap: var(--s4);
    width: 100%; max-width: 240px;
  }

  .level-share-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 3px 8px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-muted);
    font-size: 10px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }

  .level-share-btn:hover {
    border-color: var(--xp);
    color: var(--xp);
  }

  .stat { display: flex; flex-direction: column; align-items: center; flex: 1; gap: 2px; }
  .stat-value { font-size: 20px; font-weight: 300; color: var(--text-primary); line-height: 1; }
  .stat-divider { width: 1px; height: 32px; background: var(--border); }

  /* ── Right panel — identical to original ── */
  .activity-section {
    display: flex; flex-direction: column; overflow-y: auto;
  }

  .recent-notes { flex: 1; }

  .section-divider {
    border: 0;
    height: 1px;
    margin: 0;
    background: var(--border-light);
  }

  .empty-state { padding: var(--s6) var(--s5); color: var(--text-muted); text-align: center; }

  .issues-list { display: flex; flex-direction: column; }

  .issue-item {
    display: grid; grid-template-columns: 40px 1fr auto; gap: var(--s3);
    align-items: center; padding: var(--s2) var(--s5);
    border-bottom: 1px solid var(--border-light);
    text-decoration: none; color: var(--text-primary); transition: background var(--t-normal);
  }
  .issue-item:hover { background: var(--elevated); }
  .issue-num   { color: var(--text-muted); }
  .issue-title { font-size: 13px; }
  .issue-repo  { color: var(--text-muted); font-size: 10px; white-space: nowrap; }

  /* ── Notes Grid ── */
  .fab {
    position: fixed;
    bottom: calc(var(--statusbar-h) + 24px); right: 32px;
    width: 44px; height: 44px; border-radius: 50%; padding: 0;
    display: flex; align-items: center; justify-content: center;
    z-index: var(--z-sticky); box-shadow: 0 0 0 1px var(--bg); text-decoration: none;
  }

  .github-widget {
    border: 1px solid var(--border);
    border-radius: var(--r);
    margin: 10px 0;
    background: var(--surface);
  }

  .empty-state.success { color: #238636; text-align: center; padding: 12px; }

  /* ── Responsive ── */
  @media (max-width: 768px) {
    .dashboard {
      grid-template-columns: 1fr;
      grid-template-rows: auto auto 1fr;
    }

    .plant-section {
      padding: var(--s3) var(--s3) var(--s2);
      gap: var(--s2);
    }

    .resize-handle.static {
      display: none;
    }

    .activity-section {
      overflow-y: auto;
    }

    .stats-row {
      gap: var(--s2);
      max-width: 100%;
    }

    .stat-value {
      font-size: 16px;
    }

    .stat-divider {
      height: 24px;
    }

    .module-viewport {
      width: 130px;
      height: 130px;
    }

    .fab {
      right: var(--s3);
      bottom: calc(var(--statusbar-h) + var(--s3));
    }

    .issue-item {
      grid-template-columns: 30px 1fr;
      gap: var(--s2);
      padding: var(--s2) var(--s3);
    }

    .issue-repo {
      display: none;
    }
  }

  @media (max-width: 480px) {
    .plant-section {
      padding: var(--s2);
    }

    .stats-row {
      gap: var(--s1);
    }

    .stat-value {
      font-size: 14px;
    }

    .module-viewport {
      width: 110px;
      height: 110px;
    }

    .module-label {
      min-width: 60px;
      font-size: 9px;
    }
  }

.focus-mode-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  margin-top: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--r-md, 8px);
  background: var(--surface);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}
.focus-mode-btn:hover {
  background: var(--elevated);
  border-color: var(--accent);
}
</style>
