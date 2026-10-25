<script lang="ts">
  import { Search, FilePen, Plus } from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import QuickCaptureWidget from './QuickCaptureWidget.svelte';
  import ScientificCalculator from './ScientificCalculator.svelte';
  import { notes } from '$lib/stores/notes';
  import { autoScrollTitle } from '$lib/actions/autoScrollTitle';
  import {
    openNote,
    openNew,
    openDaily,
    openMomentary,
    closeEditor,
    handleSave,
    handleDelete,
    goToPrev,
    goToNext,
    getNoteVisual,
  } from '$lib/utils/notesPage';
  import {
    search,
    showEditor,
    editingNew,
    isMomentary,
    selectedNote,
    editorNote,
    dailyInitialTitle,
    dailyNotesConfigured,
    hasPrev,
    hasNext,
    NoteEditorComp,
  } from '$lib/stores/notesUi';
  import { t } from 'svelte-i18n';
</script>

<!-- ── Editor panel ──────────────────────────────────────────────────────── -->
<div class="editor-panel">
  {#if $showEditor}
    {#key $editingNew ? ($isMomentary ? 'momentary' : 'new') : $selectedNote?.id}
      {#if $NoteEditorComp}
        <svelte:component
          this={$NoteEditorComp}
          note={$editorNote}
          momentary={$isMomentary}
          initialTitle={$dailyInitialTitle}
          hasPrev={$hasPrev}
          hasNext={$hasNext}
          on:save={handleSave}
          on:cancel={closeEditor}
          on:delete={handleDelete}
          on:prev={goToPrev}
          on:next={goToNext}
        />
      {:else}
        <div class="editor-loading caption">{$t('notesPage.editorLoading')}</div>
      {/if}
    {/key}
  {:else}
    <div class="empty-dashboard">
      <DynamicIcon name="Box" size={32} color="var(--border)" />

      <div class="dash-search-container">
        <div class="dash-search">
          <Search size={14} color="var(--text-muted)" />
          <input
            type="text"
            placeholder={$t('notesPage.searchNotePlaceholder')}
            bind:value={$search}
          />
        </div>
      </div>

      <div class="dash-quick-capture">
        <QuickCaptureWidget />
      </div>

      <div class="dash-widgets">
        <!-- Quick Note Area -->
        <div class="dash-widget quick-note-widget">
          <div class="dash-widget-title">
            <DynamicIcon name="PenTool" size={13} /> Acciones Rápidas
          </div>
          <div class="dash-action-buttons">
            <button class="dash-btn primary-dash-btn" onclick={() => openNew()}>
              <FilePen size={16} /> Crear nota nueva
            </button>
            <button
              class={`dash-btn secondary-dash-btn daily-note-btn ${$dailyNotesConfigured ? '' : 'daily-note-muted'}`}
              onclick={openDaily}
            >
              <span class="daily-note-main">
                <DynamicIcon name="Calendar" size={16} /> Nota Diaria
              </span>
              <span class="daily-note-hint">{$t('notesPage.configureDailyNote')}</span>
            </button>
            <button class="dash-btn secondary-dash-btn momentary-btn" onclick={openMomentary}>
              <Plus size={16} /> Nota Momentánea
            </button>
          </div>

          <div class="dash-divider"></div>
          <div class="dash-widget-title"><DynamicIcon name="History" size={13} /> Recientes</div>
          <div class="recent-list">
            {#each $notes.slice(0, 3) as note}
              {@const vis = getNoteVisual(note)}
              <button class="recent-item" onclick={() => openNote(note)}>
                <DynamicIcon
                  name={vis.icon}
                  size={12}
                  color={vis.color || 'var(--text-disabled)'}
                  pack={vis.pack}
                />
                <span class="recent-name" use:autoScrollTitle={note.title}>
                  <span class="recent-name-text">{note.title}</span>
                </span>
                <span class="recent-time">{new Date(note.updated_at).toLocaleDateString()}</span>
              </button>
            {/each}
          </div>
        </div>

        <div class="dash-widget">
          <div class="dash-widget-title" style="margin-bottom: 5px;">
            <DynamicIcon name="Calculator" size={13} /> Calculadora
          </div>
          <ScientificCalculator />
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .editor-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
    background: var(--bg);
    min-width: 0;
  }

  /* ── Empty Dashboard ── */
  .empty-dashboard {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: start;
    height: 100%;
    overflow: hidden;
    gap: 16px;
    padding: 24px 32px;
    background: var(--bg);
    color: var(--text-primary);
  }
  .dash-search-container {
    width: 100%;
    max-width: 850px;
  }
  .dash-search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 18px;
    border-radius: var(--r);
    background: var(--surface);
    border: 1px solid var(--border);
    transition: all var(--t-fast);
  }
  .dash-search:focus-within {
    border-color: var(--xp);
    transform: translateY(-1px);
  }
  .dash-search input {
    border: none;
    background: transparent;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    flex: 1;
  }

  .dash-widgets {
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 16px;
    width: 100%;
    max-width: 850px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  .dash-quick-capture {
    width: 100%;
    max-width: 850px;
  }
  .dash-widget {
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: var(--r);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    min-width: 0;
  }
  .quick-note-widget {
    min-width: 0;
    overflow: hidden;
  }
  .dash-action-buttons {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .dash-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px;
    border-radius: var(--r);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    font-family: var(--font-sans);
    transition: all var(--t-fast);
    height: 42px;
  }
  .primary-dash-btn {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
    font-weight: 600;
  }
  .primary-dash-btn:hover {
    background: var(--xp-2);
    border-color: var(--xp-2);
    transform: translateY(-1px);
  }

  .secondary-dash-btn {
    background: color-mix(in srgb, var(--xp-2) 16%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 45%, transparent);
    color: var(--text-primary);
  }
  .secondary-dash-btn:hover {
    background: color-mix(in srgb, var(--xp-2) 28%, transparent);
    border-color: var(--xp-2);
  }
  .daily-note-btn {
    height: auto;
    min-height: 42px;
    padding: 10px 20px;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }
  .daily-note-main {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .daily-note-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    background: color-mix(in srgb, var(--xp-2) 10%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 25%, transparent);
    color: var(--text-disabled);
    transform: none;
  }
  .daily-note-btn:disabled:hover {
    background: color-mix(in srgb, var(--xp-2) 10%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 25%, transparent);
    transform: none;
  }
  .daily-note-muted {
    opacity: 0.45;
    cursor: pointer;
    background: color-mix(in srgb, var(--xp-2) 10%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 25%, transparent);
    color: var(--text-disabled);
  }
  .daily-note-muted:hover {
    background: color-mix(in srgb, var(--xp-2) 18%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 35%, transparent);
  }
  .daily-note-hint {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .momentary-btn {
    background: color-mix(in srgb, var(--xp-3) 14%, transparent);
    border-color: color-mix(in srgb, var(--xp-3) 45%, transparent);
    color: var(--text-secondary);
    border-style: solid;
  }
  .momentary-btn:hover {
    background: color-mix(in srgb, var(--xp-3) 24%, transparent);
    border-color: var(--xp-3);
    color: var(--text-primary);
  }

  .dash-divider {
    height: 1px;
    background: var(--border-light);
    margin: 5px 0;
  }

  .recent-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .recent-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: var(--bg);
    border: 1px solid var(--border-light);
    border-radius: 6px;
    cursor: pointer;
    transition: all var(--t-fast);
    text-align: left;
    min-width: 0;
    width: 100%;
  }
  .recent-item:hover {
    border-color: var(--border);
    background: var(--surface);
  }
  .recent-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    font-size: 12px;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .recent-name-text {
    display: inline-block;
    white-space: nowrap;
    transform: translateX(0);
    will-change: transform;
  }
  .recent-name-text.is-overflowing {
    animation: recent-name-marquee var(--scroll-duration, 8s) ease-in-out infinite alternate;
  }
  @keyframes recent-name-marquee {
    from {
      transform: translateX(0);
    }
    to {
      transform: translateX(calc(var(--scroll-distance, 0px) * -1));
    }
  }
  .recent-time {
    font-size: 10px;
    color: var(--text-disabled);
    font-family: var(--font-mono);
  }
</style>
