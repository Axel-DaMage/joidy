<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import TagChip from './TagChip.svelte';
  import type { Note } from '$lib/api';

  export let note: Note;
  export let active = false;

  const dispatch = createEventDispatcher<{ select: Note; delete: number }>();

  function formatDate(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return 'hoy';
    if (diffDays === 1) return 'ayer';
    if (diffDays < 7) return `hace ${diffDays} días`;
    return d.toLocaleDateString('es', { day: 'numeric', month: 'short' });
  }
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="note-card" class:active on:click={() => dispatch('select', note)}>
  <div class="note-header">
    <span class="note-title truncate">{note.title}</span>
    <span class="note-date caption">{formatDate(note.created_at)}</span>
  </div>
  {#if note.tags.length > 0}
    <div class="note-tags">
      {#each note.tags.slice(0, 4) as tag}
        <TagChip {tag} />
      {/each}
      {#if note.tags.length > 4}
        <span class="caption">+{note.tags.length - 4}</span>
      {/if}
    </div>
  {/if}
  {#if note.source === 'obsidian'}
    <span class="source-badge caption">obsidian</span>
  {/if}
</div>

<style>
  .note-card {
    padding: var(--s3) var(--s4);
    border-bottom: 1px solid var(--border-light);
    cursor: pointer;
    transition: background var(--t-normal);
    position: relative;
  }

  .note-card:hover { background: var(--elevated); }
  .note-card.active { background: var(--elevated); border-left: 2px solid var(--text-secondary); }

  .note-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--s3);
    margin-bottom: 4px;
  }

  .note-title {
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 400;
  }

  .note-date {
    flex-shrink: 0;
  }

  .note-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
  }

  .source-badge {
    position: absolute;
    top: var(--s2);
    right: var(--s3);
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.05em;
    font-family: var(--font-mono);
  }
</style>
