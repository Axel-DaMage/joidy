<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
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
  import TimeWidget from '$lib/components/TimeWidget.svelte';
  import Widget         from '$lib/components/Widget.svelte';
  import { totalXP, currentStreak, lastActivity } from '$lib/stores/gamification';
  import { notes, loadNotes, notesLoadedOnce } from '$lib/stores/notes';
  import { dashboardLayout } from '$lib/stores/layout';
  import { accentColors } from '$lib/stores/settings';
  import { api } from '$lib/api';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { captureSnapshot, getSnapshot } from '$lib/stores/pageSnapshots';

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

  function getPrBadgeInfo(pr: any): { icon: string; color: string } {
    if (pr.merged_at) return { icon: 'GitMerge', color: '#8250DF' };
    if (pr.state === 'open') return { icon: 'GitPullRequest', color: '#238636' };
    return { icon: 'XCircle', color: '#F85149' };
  }

  function getIssueInfo(issue: any): { icon: string; color: string } {
    if (issue.state === 'open') return { icon: 'CircleDot', color: '#238636' };
    return { icon: 'Circle', color: '#8250DF' };
  }

  async function loadGitHubData(filter: string = 'created') {
    if (!githubConnected) return;
    githubLoading = true;
    try {
      const [issuesRes, pullsRes] = await Promise.all([
        api.github.issues(filter),
        api.github.pulls(filter)
      ]);
      githubIssues = (issuesRes.issues || []).slice(0, 5);
      issueStats = issuesRes.stats || { open: 0, total: 0 };
      githubPRs = (pullsRes.pulls || []).slice(0, 5);
      prStats = pullsRes.stats || { open: 0, total: 0 };
      console.log('GitHub loaded:', { githubIssues, issueStats, filter });
    } catch (e) { 
      console.error('GitHub error:', e); 
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

  $: recentNotes = $notes.slice(0, 5);

  onMount(() => {
    const snap = getSnapshot('/');
    if (snap) {
      moduleIdx = snap.state.moduleIdx ?? 0;
      slideDir = snap.state.slideDir ?? 1;
    }
    
    dashboardLayout.init();

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
          await loadGitHubData('created');
          const reposRes = await api.github.repos();
          repoColors = Object.fromEntries((reposRes.repos || []).map((r: any) => [r.full_name, r.color || '#6366F1']));
        }
      } catch (e) { console.error('GitHub error:', e); }
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

  // Widget renderers per panel
  function leftWidgets(layout: typeof $dashboardLayout) { return layout.left; }
  function rightWidgets(layout: typeof $dashboardLayout) { return layout.right; }

  // Resizable panel synced with notes
  let panelWidth = 260;
</script>

<div class="dashboard" style="--panel-w: {panelWidth}px">

  <!-- ── Left panel ─────────────────────────────────────────────────────────── -->
  <section class="plant-section">

    {#each $dashboardLayout.left as wid, i (wid)}
      <Widget id={wid} panel="left" index={i} total={$dashboardLayout.left.length}>

        {#if wid === 'plant-carousel'}
          <div class="widget-centered">
            <!-- Module navigation -->
            <div class="module-nav">
              <button class="nav-arrow" on:click={prevModule} title="Anterior"><DynamicIcon name="ChevronLeft" size={14}/></button>
              <span class="module-label mono">{MODULES[moduleIdx].label.toUpperCase()}</span>
              <button class="nav-arrow" on:click={nextModule} title="Siguiente"><DynamicIcon name="ChevronRight" size={14}/></button>
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
                  on:click={() => { slideDir = idx > moduleIdx ? 1 : -1; moduleIdx = idx; }}
                  aria-label={MODULES[idx].label}
                ></button>
              {/each}
            </div>

            {#if isWilted}
              <div class="wilt-notice">
                <span style="font-size:11px; color: var(--text-muted);">Tu planta tiene sed. Escribe algo hoy.</span>
              </div>
            {/if}
          </div>

        {:else if wid === 'stats-xp'}
          <div class="widget-centered">
            <!-- XPBar moved to footer -->
            <div class="stats-row">
              <div class="stat">
                <span class="stat-value mono">{$currentStreak}</span>
                <span class="stat-label label">días</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat">
                <span class="stat-value mono">{$totalXP.toLocaleString()}</span>
                <span class="stat-label label">xp</span>
              </div>
              <div class="stat-divider"></div>
              <div class="stat">
                <span class="stat-value mono">{$notes.length}</span>
                <span class="stat-label label">notas</span>
              </div>
            </div>
          </div>

        {:else if wid === 'time-widget'}
          <TimeWidget />

        {:else if wid === 'pomodoro'}
          <PomodoroWidget />

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
                <NoteCard {note} on:select={() => goto(`/notes?id=${note.id}`)} />
              {/each}
            {/if}
          </div>

        {:else if wid === 'github-issues'}
          {#if githubConnected}
            <div class="section-header">
              <h4 style="color: {$accentColors[1]}">GitHub</h4>
              {#if !githubLoading}
                <div class="gh-filters">
                  <div class="gh-filter">
                    <button class="filter-btn" class:active={ghType === 'all'} on:click={() => setGhType('all')}>Todo</button>
                    <button class="filter-btn" class:active={ghType === 'issues'} on:click={() => setGhType('issues')}>Issues</button>
                    <button class="filter-btn" class:active={ghType === 'prs'} on:click={() => setGhType('prs')}>PRs</button>
                  </div>
                  <span class="gh-filter-divider">|</span>
                  <div class="gh-filter">
                    <button class="filter-btn" class:active={ghFilter === 'created'} on:click={() => setGhFilter('created')}>Creados</button>
                    <button class="filter-btn" class:active={ghFilter === 'assigned'} on:click={() => setGhFilter('assigned')}>Asignados</button>
                  </div>
                </div>
              {/if}
            </div>
            {#if githubLoading}
              <div class="empty-state"><span class="caption">Cargando...</span></div>
            {:else if githubIssues.length > 0 || githubPRs.length > 0}
              <div class="github-list">
                {#if ghType === 'all' || ghType === 'prs'}
                  {#each githubPRs as pr}
                    {@const prInfo = getPrBadgeInfo(pr)}
                    <a href={pr.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[pr.repo] || $accentColors[1]}">
                      <span class="gh-badge-icon"><DynamicIcon name={prInfo.icon} size={14} color={prInfo.color} /></span>
                      <div class="gh-info">
                        <span class="gh-title truncate">{pr.title}</span>
                        <span class="gh-meta mono">{pr.repo} #{pr.number}</span>
                      </div>
                    </a>
                  {/each}
                {/if}
                {#if ghType === 'all' || ghType === 'issues'}
                  {#each githubIssues as issue}
                    {@const issueInfo = getIssueInfo(issue)}
                    <a href={issue.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[issue.repo] || $accentColors[1]}">
                      <span class="gh-badge-icon"><DynamicIcon name={issueInfo.icon} size={14} color={issueInfo.color} /></span>
                      <div class="gh-info">
                        <span class="gh-title truncate">{issue.title}</span>
                        <span class="gh-meta mono">{issue.repo} #{issue.number}</span>
                      </div>
                    </a>
                  {/each}
                {/if}
              </div>
            {:else}
              <div class="github-summary" style="padding: 20px;">
                <div class="stat"><span class="stat-value mono">{issueStats.open + prStats.open}</span><span class="stat-label label">open</span></div>
                <div class="stat-divider"></div>
                <div class="stat"><span class="stat-value mono">{issueStats.total}</span><span class="stat-label label">issues</span></div>
                <div class="stat-divider"></div>
                <div class="stat"><span class="stat-value mono">{prStats.total}</span><span class="stat-label label">prs</span></div>
              </div>
              <div class="empty-state success">✓ Sin pendientes</div>
            {/if}
          {:else}
            <div class="section-header"><h4 style="color: {$accentColors[1]}">GitHub</h4></div>
            <div class="empty-state"><span class="caption">Conecta GitHub</span></div>
          {/if}
        {/if}

      </Widget>
    {/each}

  </section>

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <div class="resize-handle static"></div>

  <!-- ── Right panel ────────────────────────────────────────────────────────── -->
  <section class="activity-section">

    {#each $dashboardLayout.right as wid, i (wid)}
      <Widget id={wid} panel="right" index={i} total={$dashboardLayout.right.length}>

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
                <NoteCard {note} on:select={() => goto(`/notes?id=${note.id}`)} />
              {/each}
            {/if}
          </div>
          <hr class="section-divider" />

        {:else if wid === 'github-issues'}
          {#if githubConnected}
            {#if githubLoading}
              <div class="section-header"><h4 style="color: {$accentColors[1]}">GitHub</h4></div>
              <div class="empty-state"><span class="caption">Cargando...</span></div>
            {:else if githubIssues.length > 0 || githubPRs.length > 0}
              <div class="section-header">
                <h4 style="color: {$accentColors[1]}">GitHub</h4>
                <div class="gh-filters">
                  <div class="gh-filter" style="gap:4px">
                    <button class="filter-btn" class:active={ghType === 'all'} on:click={() => setGhType('all')}>Todo</button>
                    <button class="filter-btn" class:active={ghType === 'issues'} on:click={() => setGhType('issues')}>Issues</button>
                    <button class="filter-btn" class:active={ghType === 'prs'} on:click={() => setGhType('prs')}>PRs</button>
                  </div>
                  <span class="gh-filter-divider">|</span>
                  <div class="gh-filter" style="gap:4px">
                    <button class="filter-btn" class:active={ghFilter === 'created'} on:click={() => setGhFilter('created')}>Creados</button>
                    <button class="filter-btn" class:active={ghFilter === 'assigned'} on:click={() => setGhFilter('assigned')}>Asignados</button>
                  </div>
                </div>
              </div>
              <div class="github-list">
                {#if ghType === 'all' || ghType === 'prs'}
                  {#each githubPRs as pr}
                    {@const prInfo = getPrBadgeInfo(pr)}
                    <a href={pr.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[pr.repo] || $accentColors[1]}">
                      <span class="gh-badge-icon"><DynamicIcon name={prInfo.icon} size={14} color={prInfo.color} /></span>
                      <div class="gh-info">
                        <span class="gh-title truncate">{pr.title}</span>
                        <span class="gh-meta mono">{pr.repo} #{pr.number}</span>
                      </div>
                    </a>
                  {/each}
                {/if}
                {#if ghType === 'all' || ghType === 'issues'}
                  {#each githubIssues as issue}
                    {@const issueInfo = getIssueInfo(issue)}
                    <a href={issue.url} target="_blank" rel="noopener" class="gh-item" style="--repo-color: {repoColors[issue.repo] || $accentColors[1]}">
                      <span class="gh-badge-icon"><DynamicIcon name={issueInfo.icon} size={14} color={issueInfo.color} /></span>
                      <div class="gh-info">
                        <span class="gh-title truncate">{issue.title}</span>
                        <span class="gh-meta mono">{issue.repo} #{issue.number}</span>
                      </div>
                    </a>
                  {/each}
                {/if}
              </div>
            {:else}
              <div class="section-header"><h4 style="color: {$accentColors[1]}">GitHub</h4></div>
              <div class="empty-state"><span class="caption">Sin issues</span></div>
            {/if}
          {/if}

        {:else if wid === 'plant-carousel'}
          <div class="widget-centered">
            <div class="module-nav">
              <button class="nav-arrow" on:click={prevModule}><DynamicIcon name="ChevronLeft" size={14}/></button>
              <span class="module-label mono">{MODULES[moduleIdx].label.toUpperCase()}</span>
              <button class="nav-arrow" on:click={nextModule}><DynamicIcon name="ChevronRight" size={14}/></button>
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
              <div class="stat"><span class="stat-value mono">{$totalXP.toLocaleString()}</span><span class="stat-label label">xp</span></div>
              <div class="stat-divider"></div>
              <div class="stat"><span class="stat-value mono">{$notes.length}</span><span class="stat-label label">notas</span></div>
            </div>
          </div>

        {:else if wid === 'time-widget'}
          <TimeWidget />

        {:else if wid === 'pomodoro'}
          <PomodoroWidget />
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

  .stat { display: flex; flex-direction: column; align-items: center; flex: 1; gap: 2px; }
  .stat-value { font-size: 20px; font-weight: 300; color: var(--text-primary); line-height: 1; }
  .stat-divider { width: 1px; height: 32px; background: var(--border); }

  /* ── Right panel — identical to original ── */
  .activity-section {
    display: flex; flex-direction: column; overflow-y: auto;
  }

  .section-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: var(--s4) var(--s5);
    border-bottom: 1px solid var(--border-light);
    position: sticky; top: 0; background: var(--bg); z-index: 1;
  }

  .section-header h4 {
    color: var(--text-secondary); font-weight: 400; font-size: 12px; letter-spacing: 0.04em;
  }

  .recent-notes { flex: 1; }

  .section-divider { border: none; border-top: 1px solid var(--border-light); margin: 0; }

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
    z-index: 50; box-shadow: 0 0 0 1px var(--bg); text-decoration: none;
  }

  .github-widget {
    border: 1px solid var(--border);
    border-radius: var(--r);
    margin: 10px 0;
    background: var(--surface);
  }

  .gh-filter {
    display: flex; gap: 6px;
  }
  .gh-filters {
    display: flex; flex-direction: row; gap: 8px; align-items: center;
  }
  .gh-filter-divider {
    color: var(--border); font-size: 12px;
  }
  .filter-btn {
    font-size: 10px; padding: 4px 10px; border-radius: 4px;
    background: transparent; border: 1px solid var(--border-light);
    color: var(--text-muted); cursor: pointer; transition: all var(--t-fast);
    min-width: 60px; height: 24px; display: flex; align-items: center; justify-content: center;
  }
  .filter-btn:hover { border-color: var(--border); color: var(--text-secondary); }
.filter-btn.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast-text, white);
  }

  .github-list { display: flex; flex-direction: column; }
  .gh-item {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; border-bottom: 1px solid var(--border-light);
    text-decoration: none; color: var(--text-primary);
  }
  .gh-item:hover { background: var(--elevated); }
  .gh-badge {
    font-size: 10px; padding: 2px 5px; border-radius: 4px;
    font-weight: 600; min-width: 24px; text-align: center;
  }
  .gh-badge.pr { background: #238636; color: white; }
  .gh-badge.pr.open { background: #238636; color: white; }
  .gh-badge.pr.closed { background: #F85149; color: white; }
  .gh-badge.pr.merged { background: #8250DF; color: white; }
  .gh-badge.issue { background: var(--border-light); color: var(--text-secondary); }
  .gh-badge-icon { display: flex; align-items: center; justify-content: center; min-width: 24px; }
  .gh-info { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .gh-title { flex: 1; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .gh-meta { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
  .github-summary { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 16px; }
  .stat { display: flex; flex-direction: column; align-items: center; gap: 2px; }
  .stat-value { font-size: 18px; font-weight: 600; }
  .stat-label { font-size: 10px; color: var(--text-muted); text-transform: uppercase; }
  .stat-divider { width: 1px; height: 30px; background: var(--border-light); }
  .empty-state.success { color: #238636; text-align: center; padding: 12px; }
</style>
