<script lang="ts">
  // @ts-nocheck
  import { createEventDispatcher } from 'svelte';
  import { goto } from '$app/navigation';
  import TagChip from './TagChip.svelte';
  import { findNoteByTitle } from '$lib/stores/notes';
  import { folderMetaStore, updateFolderMeta } from '$lib/stores/settings';
  import { Settings } from 'lucide-svelte';
  import type { Note } from '$lib/api';
  import DynamicIcon from './DynamicIcon.svelte';
  import { extractFrontmatter, getFileIcon } from '$lib/utils/fileTree';

  export let note: Note;
  export let active = false;
  export let showTags = true;
  export let selected = false;
  export let bulkMode = false;

  const dispatch = createEventDispatcher<{ select: Note; delete: number; customize: { path: string; icon: string | null; color: string | null; note?: Note }; toggleSelect: number }>();

  function formatDate(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays <= 0) return 'hoy';   // ≤0 handles timezone-naive UTC strings
    if (diffDays === 1) return 'ayer';
    if (diffDays < 7) return `hace ${diffDays} días`;
    return d.toLocaleDateString('es', { day: 'numeric', month: 'short' });
  }

  function getFileMeta() {
    const key = note.source_path || `note-${note.id}`;
    const meta = $folderMetaStore[key] || {};
    const fm = extractFrontmatter(note.content || '');
    return {
      icon: meta.icon || fm.icon || getFileIcon(note.title, note.content || ''),
      color: meta.color || fm.color || undefined,
      pack: fm.pack || undefined,
    };
  }

  function getMetaKey(): string {
    return note.source_path || `note-${note.id}`;
  }

  function onCustomize(e: Event) {
    e.stopPropagation();
    dispatch('customize', { 
      path: getMetaKey(), 
      icon: getFileMeta().icon, 
      color: getFileMeta().color,
      note: note
    });
  }

  $: meta = getFileMeta();
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  class="note-card"
  class:active
  class:bulk-selected={selected}
  on:click={() => bulkMode ? dispatch('toggleSelect', note.id) : dispatch('select', note)}
>
  <div class="note-header">
    {#if bulkMode}
      <input
        type="checkbox"
        class="note-checkbox"
        checked={selected}
        on:click|stopPropagation
        on:change={() => dispatch('toggleSelect', note.id)}
      />
    {/if}
    <div class="note-icon"><DynamicIcon name={meta.icon} size={12} color={meta.color} pack={meta.pack} /></div>
    <span class="note-title truncate">{note.title}</span>
    <span class="note-date caption">{formatDate(note.created_at)}</span>
    {#if !bulkMode}
      <button type="button" class="note-settings-btn" title="Personalizar" on:click={onCustomize}>
        <Settings size={10} />
      </button>
    {/if}
  </div>
  {#if showTags && note.tags.length > 0}
    <div class="note-tags">
      {#each note.tags.slice(0, 4) as tag}
        <TagChip {tag} on:click={(e) => {
          const linkedNote = findNoteByTitle(e.detail);
          if (linkedNote) {
            goto(`/notes?id=${linkedNote.id}`);
          }
        }} />
      {/each}
      {#if note.tags.length > 4}
        <span class="caption">+{note.tags.length - 4}</span>
      {/if}
    </div>
  {/if}

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
  .note-card.bulk-selected { background: var(--elevated); border-left: 2px solid var(--accent); }

  .note-header {
    display: flex;
    align-items: center;
    gap: var(--s3);
    margin-bottom: 4px;
  }

  .note-title {
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 400;
    flex: 1;
  }

  .note-date {
    flex-shrink: 0;
  }

  .note-icon {
    flex-shrink: 0;
    margin-right: 4px;
  }

  .note-checkbox {
    flex-shrink: 0;
    width: 14px;
    height: 14px;
    accent-color: var(--accent);
    cursor: pointer;
  }

  .note-settings-btn {
    flex-shrink: 0;
    display: none;
    padding: 2px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 3px;
  }

  .note-card:hover .note-settings-btn {
    display: flex;
  }

  .note-settings-btn:hover {
    color: var(--accent);
    background: var(--border-light);
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
