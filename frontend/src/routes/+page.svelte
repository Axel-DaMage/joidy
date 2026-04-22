<script lang="ts">
  import { onMount } from 'svelte';
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
  import { notes, loadNotes } from '$lib/stores/notes';
  import { dashboardLayout, editMode } from '$lib/stores/layout';
  import { api } from '$lib/api';

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

  function prevModule() { slideDir = -1; moduleIdx = (moduleIdx - 1 + MODULES.length) % MODULES.length; }
  function nextModule() { slideDir =  1; moduleIdx = (moduleIdx + 1) % MODULES.length; }

  // ── Data ───────────────────────────────────────────────────────────────────
  let githubConnected = false;
  let githubIssues: { id: number; number: number; title: string; repo: string; url: string }[] = [];

  $: isWilted = (() => {
    if (!$lastActivity) return false;
    const last = new Date($lastActivity);
    if (isNaN(last.getTime())) return false;
    return (Date.now() - last.getTime()) / 86400000 > 2;
  })();

  $: recentNotes = $notes.slice(0, 5);

  onMount(async () => {
    dashboardLayout.init();
    await loadNotes();
    try {
      const status = await api.github.status();
      githubConnected = status.connected;
      if (githubConnected) githubIssues = (await api.github.issues()).slice(0, 3);
    } catch (_) {}
  });

  // Widget renderers per panel
  function leftWidgets(layout: typeof $dashboardLayout) { return layout.left; }
  function rightWidgets(layout: typeof $dashboardLayout) { return layout.right; }
</script>

<div class="dashboard">

  <!-- ── Edit mode bar ─────────────────────────────────────────────────────── -->
  {#if $editMode}
    <div class="edit-bar" transition:fly={{ y: -20, duration: 160 }}>
      <span class="mono edit-bar-title">MODO EDICIÓN</span>
      <span class="edit-bar-hint">Usa las flechas de cada widget para moverlos</span>
      <button class="btn-reset mono" on:click={dashboardLayout.reset}><RotateCcw size={10}/> reset</button>
      <button class="btn-done"       on:click={() => editMode.set(false)}>Listo</button>
    </div>
  {/if}

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
            <h4>Notas recientes</h4>
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
          {#if githubConnected && githubIssues.length > 0}
            <div class="section-header"><h4>GitHub — Issues asignados</h4></div>
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
        {/if}

      </Widget>
    {/each}

  </section>

  <!-- ── Right panel ────────────────────────────────────────────────────────── -->
  <section class="activity-section">

    {#each $dashboardLayout.right as wid, i (wid)}
      <Widget id={wid} panel="right" index={i} total={$dashboardLayout.right.length}>

        {#if wid === 'recent-notes'}
          <div class="section-header">
            <h4>Notas recientes</h4>
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
          {#if githubConnected && githubIssues.length > 0}
            <div class="section-header"><h4>GitHub — Issues asignados</h4></div>
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
    grid-template-columns: 320px 1fr;
    height: 100%;
    position: relative;
  }

  /* ── Edit bar ── */
  .edit-bar {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 6px 16px;
    background: color-mix(in srgb, var(--xp) 6%, var(--surface));
    border-bottom: 1px solid color-mix(in srgb, var(--xp) 25%, var(--border));
    font-size: 11px;
  }

  .edit-bar-title { font-size: 9px; letter-spacing: 0.12em; color: var(--xp); }
  .edit-bar-hint  { color: var(--text-muted); }

  .btn-reset {
    display: flex; align-items: center; gap: 4px;
    padding: 3px 8px; font-size: 10px;
    background: transparent; color: var(--text-muted);
    border: 1px solid var(--border); border-radius: 3px; cursor: pointer;
  }
  .btn-reset:hover { color: var(--text-secondary); }

  .btn-done {
    margin-left: auto;
    padding: 3px 12px; font-size: 11px; font-family: var(--font-mono);
    background: var(--xp); color: var(--bg);
    border: none; border-radius: 3px; cursor: pointer; letter-spacing: 0.05em;
  }

  /* ── Left panel — identical to original ── */
  .plant-section {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--s4) var(--s5) var(--s4);
    border-right: 1px solid var(--border);
    gap: 10px;
    overflow: hidden;
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
    padding: 6px 0;
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
</style>
