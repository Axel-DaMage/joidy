<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { Plus } from 'lucide-svelte';
  import Plant from '$lib/components/Plant.svelte';
  import XPBar from '$lib/components/XPBar.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import { totalXP, currentStreak, plantStageName, plantProgress, lastActivity } from '$lib/stores/gamification';
  import { notes, loadNotes } from '$lib/stores/notes';
  import { api } from '$lib/api';

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
  <!-- Left: Plant + Stats -->
  <section class="plant-section">
    <div class="plant-stage-label label" style="margin-bottom: 8px; text-align:center;">
      {$plantStageName.toUpperCase()}
    </div>

    <div class="plant-wrapper">
      <Plant size={220} wilted={isWilted} />
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
    padding: var(--s6) var(--s5);
    border-right: 1px solid var(--border);
    gap: var(--s4);
    overflow-y: auto;
  }

  .plant-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--s4) 0;
  }

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
