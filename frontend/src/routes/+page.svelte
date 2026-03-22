<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { fly } from 'svelte/transition';
  import { Plus, ChevronLeft, ChevronRight } from 'lucide-svelte';
  import Plant         from '$lib/components/Plant.svelte';
  import GalaxyModule  from '$lib/components/GalaxyModule.svelte';
  import MountainModule from '$lib/components/MountainModule.svelte';
  import CityModule    from '$lib/components/CityModule.svelte';
  import OrbitModule   from '$lib/components/OrbitModule.svelte';
  import XPBar         from '$lib/components/XPBar.svelte';
  import NoteCard      from '$lib/components/NoteCard.svelte';
  import PomodoroWidget from '$lib/components/PomodoroWidget.svelte';
  import { totalXP, currentStreak, plantStageName, plantProgress, lastActivity } from '$lib/stores/gamification';
  import { notes, loadNotes } from '$lib/stores/notes';
  import { api } from '$lib/api';

  // ── Module carousel ────────────────────────────────────────────────────────
  const MODULES = [
    { id: 'planta',   label: 'Planta'   },
    { id: 'galaxia',  label: 'Galaxia'  },
    { id: 'montana',  label: 'Montaña'  },
    { id: 'ciudad',   label: 'Ciudad'   },
    { id: 'orbita',   label: 'Órbita'   },
  ];

  let moduleIdx  = 0;
  let slideDir   = 1; // 1=right, -1=left

  function prevModule() {
    slideDir  = -1;
    moduleIdx = (moduleIdx - 1 + MODULES.length) % MODULES.length;
  }
  function nextModule() {
    slideDir  = 1;
    moduleIdx = (moduleIdx + 1) % MODULES.length;
  }

  let githubConnected = false;
  let githubIssues: { id: number; number: number; title: string; repo: string; url: string }[] = [];

  $: isWilted = (() => {
    if (!$lastActivity) return false;
    const last = new Date($lastActivity);
    if (isNaN(last.getTime())) return false;
    const diffDays = (Date.now() - last.getTime()) / 86400000;
    return diffDays > 2;
  })();

  $: recentNotes = $notes.slice(0, 5);

  onMount(async () => {
    await loadNotes();
    try {
      const status = await api.github.status();
      githubConnected = status.connected;
      if (githubConnected) {
        githubIssues = (await api.github.issues()).slice(0, 3);
      }
    } catch (_) {}
  });
</script>

<div class="dashboard">
  <!-- Left: Module carousel + Stats + Pomodoro -->
  <section class="plant-section">

    <!-- Module navigation -->
    <div class="module-nav">
      <button class="nav-arrow" on:click={prevModule} title="Anterior">
        <ChevronLeft size={14} />
      </button>
      <span class="module-label mono">{MODULES[moduleIdx].label.toUpperCase()}</span>
      <button class="nav-arrow" on:click={nextModule} title="Siguiente">
        <ChevronRight size={14} />
      </button>
    </div>

    <!-- Module viewport -->
    <div class="module-viewport">
      {#key moduleIdx}
        <div
          class="module-slide"
          in:fly={{ x: slideDir * 40, duration: 220, opacity: 0 }}
        >
          {#if MODULES[moduleIdx].id === 'planta'}
            <Plant size={200} wilted={isWilted} />
          {:else if MODULES[moduleIdx].id === 'galaxia'}
            <GalaxyModule size={200} />
          {:else if MODULES[moduleIdx].id === 'montana'}
            <MountainModule size={200} />
          {:else if MODULES[moduleIdx].id === 'ciudad'}
            <CityModule size={200} />
          {:else if MODULES[moduleIdx].id === 'orbita'}
            <OrbitModule size={200} />
          {/if}
        </div>
      {/key}
    </div>

    <!-- Module dots -->
    <div class="module-dots">
      {#each MODULES as _, i}
        <button
          class="dot"
          class:active={i === moduleIdx}
          on:click={() => { slideDir = i > moduleIdx ? 1 : -1; moduleIdx = i; }}
        ></button>
      {/each}
    </div>

    <div class="xp-section">
      <XPBar />
    </div>

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

    {#if isWilted}
      <div class="wilt-notice">
        <span style="font-size:11px; color: var(--text-muted);">Tu planta tiene sed. Escribe algo hoy.</span>
      </div>
    {/if}

    <!-- Clock + Pomodoro timer -->
    <PomodoroWidget />
  </section>

  <!-- Right: Recent notes + GitHub -->
  <section class="activity-section">
    <div class="section-header">
      <h4>Notas recientes</h4>
      <a href="/notes" class="btn btn-ghost" style="font-size:11px; padding: 2px 8px;">ver todas →</a>
    </div>

    <div class="recent-notes">
      {#if recentNotes.length === 0}
        <div class="empty-state">
          <span class="caption">No hay notas aún.</span>
        </div>
      {:else}
        {#each recentNotes as note}
          <NoteCard {note} on:select={() => goto(`/notes?id=${note.id}`)} />
        {/each}
      {/if}
    </div>

    {#if githubConnected && githubIssues.length > 0}
      <div class="divider"></div>
      <div class="section-header">
        <h4>GitHub — Issues asignados</h4>
      </div>
      <div class="issues-list">
        {#each githubIssues as issue}
          <a href={issue.url} target="_blank" rel="noopener" class="issue-item">
            <span class="issue-num mono caption">#{issue.number}</span>
            <span class="issue-title truncate">{issue.title}</span>
            <span class="issue-repo caption">{issue.repo}</span>
          </a>
        {/each}
      </div>
    {/if}
  </section>

  <!-- FAB: new note -->
  <a href="/notes?new=1" class="fab btn btn-primary" title="Nueva nota">
    <Plus size={16} />
  </a>
</div>

<style>
  .dashboard {
    display: grid;
    grid-template-columns: 320px 1fr;
    height: 100%;
    position: relative;
  }

  /* ── Plant section ── */
  .plant-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--s4) var(--s5) var(--s4);
    border-right: 1px solid var(--border);
    gap: 10px;
    overflow-y: auto;
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
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
    flex-shrink: 0;
  }
  .nav-arrow:hover  { border-color: var(--text-muted); color: var(--text-secondary); }
  .nav-arrow:active { transform: scale(0.93); }

  /* ── Module viewport ── */
  .module-viewport {
    width: 220px;
    height: 220px;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .module-slide {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* ── Navigation dots ── */
  .module-dots {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--border);
    border: none;
    padding: 0;
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .dot.active { background: var(--text-muted); width: 14px; border-radius: 3px; }

  .xp-section {
    width: 100%;
    max-width: 240px;
  }

  .stats-row {
    display: flex;
    align-items: center;
    gap: var(--s4);
    width: 100%;
    max-width: 240px;
  }

  .stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    gap: 2px;
  }

  .stat-value {
    font-size: 20px;
    font-weight: 300;
    color: var(--text-primary);
    line-height: 1;
  }

  .stat-divider {
    width: 1px;
    height: 32px;
    background: var(--border);
  }

  .wilt-notice {
    padding: var(--s2) var(--s3);
    border: 1px solid var(--border);
    border-radius: var(--r);
    text-align: center;
  }

  /* ── Activity section ── */
  .activity-section {
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s4) var(--s5);
    border-bottom: 1px solid var(--border-light);
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 1;
  }

  .section-header h4 {
    color: var(--text-secondary);
    font-weight: 400;
    font-size: 12px;
    letter-spacing: 0.04em;
  }

  .recent-notes {
    flex: 1;
  }

  .empty-state {
    padding: var(--s6) var(--s5);
    color: var(--text-muted);
    text-align: center;
  }

  /* ── GitHub issues ── */
  .issues-list { display: flex; flex-direction: column; }

  .issue-item {
    display: grid;
    grid-template-columns: 40px 1fr auto;
    gap: var(--s3);
    align-items: center;
    padding: var(--s2) var(--s5);
    border-bottom: 1px solid var(--border-light);
    text-decoration: none;
    color: var(--text-primary);
    transition: background var(--t-normal);
  }

  .issue-item:hover { background: var(--elevated); }
  .issue-num { color: var(--text-muted); }
  .issue-title { font-size: 13px; }
  .issue-repo { color: var(--text-muted); font-size: 10px; white-space: nowrap; }

  /* ── FAB ── */
  .fab {
    position: fixed;
    bottom: calc(var(--statusbar-h) + 24px);
    right: 32px;
    width: 44px;
    height: 44px;
    border-radius: 50%;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 50;
    box-shadow: 0 0 0 1px var(--bg);
    text-decoration: none;
  }
</style>
