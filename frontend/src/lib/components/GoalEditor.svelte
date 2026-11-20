<script lang="ts">
  // Goal Editor — container component (#935). Owns the shared `goalEditor`
  // store and orchestrates the responsive three-pane layout:
  //   ≥1200px    editor | live preview | properties
  //   768–1199px editor (or preview) stacked over the properties panel
  //   <768px     single column with a tab bar to switch panes
  // Panes (GoalEditorContent / GoalEditorPreview / GoalPropertiesPanel) read
  // and write the store directly — no prop drilling past one level.
  import { createEventDispatcher, onDestroy, onMount } from 'svelte';
  import {
    Eye,
    EyeOff,
    Save,
    Trash2,
    X,
    Maximize,
    Settings,
    CheckCircle2,
    Sun,
    Moon,
    Zap,
    Pencil,
    SlidersHorizontal,
  } from 'lucide-svelte';
  import 'highlight.js/styles/github-dark.css';
  import { api, type Goal, type GoalContext, type Note, type Tag as TagType } from '$lib/api';
  import { t } from 'svelte-i18n';
  import { logger } from '$lib/utils/logger';
  import { createTimerRegistry } from '$lib/utils/timer';
  import { loadDraft, persistDraft, clearDraft } from '$lib/utils/noteDrafts';
  import { goalEditor, type GoalEditorPane } from '$lib/stores/goalEditor.svelte';
  import NoteRecoveryBanner from './NoteRecoveryBanner.svelte';
  import GoalEditorContent from './GoalEditorContent.svelte';
  import GoalEditorPreview from './GoalEditorPreview.svelte';
  import GoalPropertiesPanel from './GoalPropertiesPanel.svelte';

  const timers = createTimerRegistry();

  const AUTOSAVE_DELAY = 2000;

  interface Props {
    goal?: Goal | null;
    /** Initial body content (markdown). After mount the store owns it. */
    content?: string;
    notes?: Note[];
    tags?: TagType[];
    onCreateNote?: (title: string) => void | Note | Promise<void | Note>;
  }

  let { goal = null, content = '', notes = [], tags = [], onCreateNote }: Props = $props();

  const dispatch = createEventDispatcher<{
    save: { title: string; content: string };
    cancel: void;
    delete: void;
    complete: void;
    edit: void;
    contextChange: { context: GoalContext; goal: Goal };
    /** Fired when the properties panel persists a field change (#935). */
    goalUpdate: { goal: Goal };
  }>();

  // ── Store sync ─────────────────────────────────────────────────────────────
  // The store is the single source of truth for panes; props flow in one way.
  $effect(() => {
    goalEditor.goal = goal ?? null;
  });
  // Only overwrite the title when the incoming goal actually carries a
  // different one (reload, goal→goal navigation). Property-panel saves swap
  // the goal object with the same title — mirroring unconditionally would
  // clobber in-progress title edits (#935).
  let lastSyncedGoal: { id: number | null; title: string } | null = null;
  $effect(() => {
    const id = goal?.id ?? null;
    const incoming = goal?.title ?? '';
    if (!lastSyncedGoal || lastSyncedGoal.id !== id || lastSyncedGoal.title !== incoming) {
      goalEditor.title = incoming;
    }
    lastSyncedGoal = { id, title: incoming };
  });
  $effect(() => {
    goalEditor.content = content ?? '';
  });

  // Reset transient pane state when navigating goal → goal without remounting
  // (the [id] page reuses this component for client-side navigation).
  let lastGoalId: number | null = null;
  $effect(() => {
    const id = goal?.id ?? null;
    if (id !== lastGoalId) {
      lastGoalId = id;
      goalEditor.previewMode = false;
      goalEditor.mobilePane = 'editor';
      goalEditor.deleteConfirm = false;
      goalEditor.saved = false;
    }
  });

  // ── Energy context (#1200) ────────────────────────────────────────────────
  // ANY is the default so classification stays optional. Persisted immediately
  // via the goal update endpoint.
  let goalContext = $state<GoalContext>('ANY');

  $effect(() => {
    goalContext = goal?.context ?? 'ANY';
  });

  const CONTEXT_OPTIONS: GoalContext[] = ['ANY', 'MORNING', 'NIGHT'];
  const CONTEXT_LABEL_KEYS: Record<GoalContext, string> = {
    ANY: 'contextAny',
    MORNING: 'contextMorning',
    NIGHT: 'contextNight',
  };
  const CONTEXT_HINT_KEYS: Record<GoalContext, string> = {
    ANY: 'contextAnyHint',
    MORNING: 'contextMorningHint',
    NIGHT: 'contextNightHint',
  };

  async function selectContext(ctx: GoalContext) {
    if (!goal || ctx === goalContext || goalEditor.contextSaving) return;
    const prev = goalContext;
    goalContext = ctx;
    goalEditor.contextSaving = true;
    try {
      const updated = await api.goals.update(goal.id, { context: ctx });
      goalEditor.goal = updated;
      dispatch('contextChange', { context: ctx, goal: updated });
    } catch (e) {
      goalContext = prev;
      logger.error('[GoalEditor] context update failed:', e);
    } finally {
      goalEditor.contextSaving = false;
    }
  }

  // ── Autosave & drafts (#1129) ──────────────────────────────────────────────
  let autosaveTimer: ReturnType<typeof setTimeout> | undefined;
  let showRecoveryPrompt = $state(false);
  let recoveredDraft = $state<{ title: string; content: string; tags: string[] } | null>(null);

  let draftKey = $derived(goal ? `joidy-goal-draft-${goal.id}` : null);

  function saveDraft() {
    if (!draftKey) return;
    // Persist even with an empty title: content typed before the goal is
    // titled must survive a reload (recovered via the banner).
    persistDraft(draftKey, {
      title: goalEditor.title.trim(),
      content: goalEditor.content,
      tags: [],
    });
  }

  function triggerAutosave() {
    goalEditor.hasUnsavedChanges = true;
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      saveDraft();
      if (goalEditor.title.trim()) handleSave();
      else goalEditor.hasUnsavedChanges = false;
    }, AUTOSAVE_DELAY);
  }

  onMount(() => {
    const draft = loadDraft(draftKey);
    if (draft && draft.content !== goalEditor.content) {
      recoveredDraft = draft;
      showRecoveryPrompt = true;
    }
  });

  function applyDraft() {
    if (recoveredDraft) {
      goalEditor.title = recoveredDraft.title;
      goalEditor.content = recoveredDraft.content;
      showRecoveryPrompt = false;
      recoveredDraft = null;
      triggerAutosave();
    }
  }

  function dismissDraft() {
    showRecoveryPrompt = false;
    recoveredDraft = null;
    if (draftKey) clearDraft(draftKey);
  }

  // Browser-level guard: warn before closing the tab with unsaved work.
  function handleBeforeUnload(e: BeforeUnloadEvent) {
    if (!goalEditor.hasUnsavedChanges) return;
    e.preventDefault();
    e.returnValue = '';
  }

  function handleDeleteClick() {
    if (!goalEditor.deleteConfirm) {
      goalEditor.deleteConfirm = true;
      timers.timeout(() => (goalEditor.deleteConfirm = false), 3000);
      return;
    }
    dispatch('delete');
  }

  // ── Zen mode (#270): sync with body class to hide layout chrome ────────────
  $effect(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.toggle('zen-mode-active', goalEditor.zenMode);
    }
  });

  onDestroy(() => {
    if (typeof document !== 'undefined') document.body.classList.remove('zen-mode-active');
    timers.clearAll();
    clearTimeout(autosaveTimer);
    saveDraft();
  });

  let wordCount = $derived(
    goalEditor.content.trim() ? goalEditor.content.trim().split(/\s+/).length : 0
  );
  let charCount = $derived(goalEditor.content.length);

  async function handleSave() {
    if (!goalEditor.title.trim()) return;
    goalEditor.saving = true;
    dispatch('save', { title: goalEditor.title.trim(), content: goalEditor.content });
    goalEditor.saving = false;
    goalEditor.saved = true;
    if (draftKey) clearDraft(draftKey);
    goalEditor.hasUnsavedChanges = false;
    timers.timeout(() => (goalEditor.saved = false), 2000);
  }

  // ── Pane switching ─────────────────────────────────────────────────────────
  function togglePreview() {
    goalEditor.previewMode = !goalEditor.previewMode;
    // Keep the mobile tab in sync so Ctrl+P is useful below 768px too.
    goalEditor.mobilePane = goalEditor.mobilePane === 'preview' ? 'editor' : 'preview';
  }

  function showEditorPane() {
    goalEditor.previewMode = false;
    goalEditor.mobilePane = 'editor';
  }

  function handleGoalUpdate(updated: Goal) {
    dispatch('goalUpdate', { goal: updated });
  }

  const PANE_ORDER: GoalEditorPane[] = ['editor', 'preview', 'properties'];

  function onTablistKeydown(e: KeyboardEvent) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const idx = PANE_ORDER.indexOf(goalEditor.mobilePane);
    const next =
      e.key === 'ArrowRight'
        ? (idx + 1) % PANE_ORDER.length
        : (idx + PANE_ORDER.length - 1) % PANE_ORDER.length;
    goalEditor.mobilePane = PANE_ORDER[next];
  }

  function onKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
      e.preventDefault();
      togglePreview();
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      if (goalEditor.zenMode) {
        goalEditor.zenMode = false;
      } else {
        dispatch('cancel');
      }
    }
  }
</script>

<svelte:window onkeydown={onKeydown} onbeforeunload={handleBeforeUnload} />

<div class="editor-shell" class:zen-mode={goalEditor.zenMode}>
  <NoteRecoveryBanner
    bind:show={showRecoveryPrompt}
    onApply={applyDraft}
    onDismiss={dismissDraft}
  />

  {#if !goalEditor.zenMode}
    <div class="toolbar">
      <div class="toolbar-left">
        {#if goal}
          <div
            class="context-selector"
            role="radiogroup"
            aria-label={$t('goalsPage.contextLabel')}
            title={$t('goalsPage.contextHelper')}
          >
            {#each CONTEXT_OPTIONS as ctx}
              <button
                class="context-chip"
                class:active={goalContext === ctx}
                role="radio"
                aria-checked={goalContext === ctx}
                disabled={goalEditor.contextSaving}
                onclick={() => selectContext(ctx)}
                title={$t(`goalsPage.${CONTEXT_HINT_KEYS[ctx]}`)}
              >
                {#if ctx === 'MORNING'}<Sun size={12} />{:else if ctx === 'NIGHT'}<Moon
                    size={12}
                  />{:else}<Zap size={12} />{/if}
                <span>{$t(`goalsPage.${CONTEXT_LABEL_KEYS[ctx]}`)}</span>
              </button>
            {/each}
          </div>
        {/if}
      </div>

      <div class="toolbar-right">
        <span class="stat">{wordCount} palabras</span>
        <span class="stat">{charCount} caracteres</span>

        <button
          class="toolbar-btn icon-only"
          class:active={goalEditor.zenMode}
          aria-pressed={goalEditor.zenMode}
          onclick={() => (goalEditor.zenMode = !goalEditor.zenMode)}
          title={$t('goalEditor.zenMode')}
          aria-label={$t('goalEditor.zenModeShort')}
        >
          <Maximize size={14} />
        </button>

        <button
          class="toolbar-btn preview-toggle"
          class:active={goalEditor.previewMode}
          aria-pressed={goalEditor.previewMode}
          onclick={togglePreview}
          title={$t('goalEditor.togglePreview')}
        >
          {#if goalEditor.previewMode}<EyeOff size={14} />{:else}<Eye size={14} />{/if}
          <span>{goalEditor.previewMode ? 'Editor' : 'Vista previa'}</span>
        </button>

        <button
          class="toolbar-btn complete-btn"
          class:completed={goal?.is_completed}
          onclick={() => dispatch('complete')}
          title={goal?.is_completed ? 'Marcar como pendiente' : 'Completar objetivo'}
        >
          <CheckCircle2 size={14} />
          <span>{goal?.is_completed ? 'Completado' : 'Completar'}</span>
        </button>

        <button
          class="toolbar-btn save-btn"
          class:saved={goalEditor.saved}
          onclick={handleSave}
          disabled={goalEditor.saving || !goalEditor.title.trim()}
          title={$t('goalEditor.save')}
        >
          <Save size={14} />
          <span class="save-status"
            >{goalEditor.saved ? 'Guardado' : goalEditor.saving ? '...' : 'Guardar'}</span
          >
        </button>

        <button
          class="toolbar-btn"
          onclick={() => dispatch('edit')}
          title={$t('goalEditor.editGoalSettings')}
        >
          <Settings size={14} />
          <span>{$t('goalEditor.settings')}</span>
        </button>

        <button
          class="toolbar-btn delete-btn"
          class:confirming={goalEditor.deleteConfirm}
          onclick={handleDeleteClick}
          title={goalEditor.deleteConfirm ? 'Haz clic de nuevo para eliminar' : 'Eliminar objetivo'}
        >
          <Trash2 size={14} />
          <span>{goalEditor.deleteConfirm ? '¿Eliminar?' : 'Eliminar'}</span>
        </button>

        <button
          class="toolbar-btn"
          onclick={() => dispatch('cancel')}
          title={$t('goalEditor.close')}
          aria-label={$t('goalEditor.close')}
        >
          <X size={14} />
        </button>
      </div>
    </div>
  {/if}

  <div class="title-row">
    <input
      class="title-input"
      bind:value={goalEditor.title}
      placeholder={$t('goalEditor.titlePlaceholder')}
      aria-label={$t('goalEditor.titlePlaceholder')}
      oninput={() => triggerAutosave()}
      onkeydown={(e) => e.key === 'Enter' && handleSave()}
    />
  </div>

  <!-- Mobile pane switcher — only rendered <768px (see .pane-tabs styles) -->
  <div
    class="pane-tabs"
    role="tablist"
    aria-label={$t('goalEditor.paneSwitcher')}
    tabindex="-1"
    onkeydown={onTablistKeydown}
  >
    <button
      type="button"
      role="tab"
      id="goal-tab-editor"
      class="pane-tab"
      class:active={goalEditor.mobilePane === 'editor'}
      aria-selected={goalEditor.mobilePane === 'editor'}
      aria-controls="goal-pane-editor"
      tabindex={goalEditor.mobilePane === 'editor' ? 0 : -1}
      onclick={() => (goalEditor.mobilePane = 'editor')}
    >
      <Pencil size={13} />
      <span>{$t('goalEditor.tabEditor')}</span>
    </button>
    <button
      type="button"
      role="tab"
      id="goal-tab-preview"
      class="pane-tab"
      class:active={goalEditor.mobilePane === 'preview'}
      aria-selected={goalEditor.mobilePane === 'preview'}
      aria-controls="goal-pane-preview"
      tabindex={goalEditor.mobilePane === 'preview' ? 0 : -1}
      onclick={() => (goalEditor.mobilePane = 'preview')}
    >
      <Eye size={13} />
      <span>{$t('goalEditor.tabPreview')}</span>
    </button>
    <button
      type="button"
      role="tab"
      id="goal-tab-properties"
      class="pane-tab"
      class:active={goalEditor.mobilePane === 'properties'}
      aria-selected={goalEditor.mobilePane === 'properties'}
      aria-controls="goal-pane-properties"
      tabindex={goalEditor.mobilePane === 'properties' ? 0 : -1}
      onclick={() => (goalEditor.mobilePane = 'properties')}
    >
      <SlidersHorizontal size={13} />
      <span>{$t('goalEditor.tabProperties')}</span>
    </button>
  </div>

  <!-- Responsive pane grid: columns/rows are driven by media queries; which
       pane is visible below 768px is driven by data-pane. -->
  <div class="panes" data-pane={goalEditor.mobilePane} class:preview-mode={goalEditor.previewMode}>
    <div
      class="pane pane-editor"
      id="goal-pane-editor"
      role="tabpanel"
      aria-labelledby="goal-tab-editor"
      aria-label={$t('goalEditor.editorPaneLabel')}
    >
      <GoalEditorContent oninput={triggerAutosave} />
    </div>
    <div
      class="pane pane-preview"
      id="goal-pane-preview"
      role="tabpanel"
      aria-labelledby="goal-tab-preview"
      aria-label={$t('goalEditor.previewPaneLabel')}
    >
      <GoalEditorPreview onrequestedit={showEditorPane} />
    </div>
    <div
      class="pane pane-properties"
      id="goal-pane-properties"
      role="tabpanel"
      aria-labelledby="goal-tab-properties"
      aria-label={$t('goalEditor.propertiesPaneLabel')}
    >
      <GoalPropertiesPanel {notes} {tags} onUpdate={handleGoalUpdate} {onCreateNote} />
    </div>
  </div>
</div>

<style>
  .editor-shell {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }

  .editor-shell.zen-mode {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: var(--z-tooltip);
    border: none;
    border-radius: 0;
    background: var(--bg);
    padding-top: 40px;
  }

  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    gap: var(--s3);
    position: relative;
    z-index: 20;
  }

  .toolbar-left,
  .toolbar-right {
    display: flex;
    align-items: center;
    gap: var(--s2);
    flex-wrap: wrap;
  }

  .context-selector {
    display: inline-flex;
    gap: 3px;
    padding: 3px;
    background: var(--surface-hover);
    border-radius: 8px;
    border: 1px solid var(--border);
  }

  .context-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 9px;
    border: 1px solid transparent;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .context-chip:hover:not(:disabled) {
    color: var(--text-primary);
  }
  .context-chip.active {
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-weight: 600;
  }
  .context-chip:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .stat {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }

  .toolbar-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-secondary);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .toolbar-btn:hover {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .toolbar-btn.active {
    border-color: var(--text-secondary);
    color: var(--text-primary);
  }
  .toolbar-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .save-btn {
    border-color: var(--accent);
    color: var(--accent);
  }
  .save-btn:hover {
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
  }
  .save-btn.saved {
    background: var(--success);
    border-color: var(--success);
    color: var(--text-primary);
  }

  .complete-btn {
    border-color: var(--success, #22c55e);
    color: var(--success, #22c55e);
  }
  .complete-btn:hover {
    background: color-mix(in srgb, var(--success, #22c55e) 15%, transparent);
  }
  .complete-btn.completed {
    background: var(--success, #22c55e);
    color: #ffffff;
  }

  .delete-btn {
    border-color: color-mix(in srgb, #ef4444 50%, var(--border));
    color: #ef4444;
  }
  .delete-btn:hover {
    background: color-mix(in srgb, #ef4444 15%, transparent);
    border-color: #ef4444;
  }
  .delete-btn.confirming {
    background: #ef4444;
    color: #ffffff;
    border-color: #ef4444;
    font-weight: 600;
  }

  .save-status {
    display: inline-block;
    min-width: 58px;
    text-align: center;
  }

  .title-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
    border-radius: var(--r-sm);
  }
  .title-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font-size: 22px;
    font-weight: 400;
    font-family: var(--font-sans);
    color: var(--text-primary);
    line-height: 1.3;
  }
  .title-input::placeholder {
    color: var(--text-muted);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 20px 24px 12px;
    border-bottom: 1px solid var(--border-light, var(--border));
    flex-shrink: 0;
  }

  /* ── Pane switcher (mobile only) ── */
  .pane-tabs {
    display: none;
    align-items: stretch;
    gap: 4px;
    padding: 6px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }

  .pane-tab {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 7px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-muted);
    font-size: 12px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .pane-tab:hover {
    color: var(--text-primary);
    background: var(--elevated);
  }
  .pane-tab.active,
  .pane-tab[aria-selected='true'] {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
    font-weight: 600;
  }
  .pane-tab:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }

  /* ── Responsive pane grid ──
     ≥1200px (default): three columns — editor | live preview | properties */
  .panes {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(260px, 320px);
  }

  .pane {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .pane-preview {
    border-left: 1px solid var(--border-light, var(--border));
    border-right: 1px solid var(--border-light, var(--border));
  }

  /* Zen mode focuses on writing: editor pane only. */
  .editor-shell.zen-mode .panes {
    grid-template-columns: 1fr;
  }
  .editor-shell.zen-mode .pane-preview,
  .editor-shell.zen-mode .pane-properties,
  .editor-shell.zen-mode .pane-tabs {
    display: none;
  }

  /* 768–1199px: editor (or preview) stacked over the properties panel */
  @media (min-width: 768px) and (max-width: 1199px) {
    .panes {
      grid-template-columns: 1fr;
      grid-template-rows: minmax(0, 1fr) auto;
    }
    .panes:not(.preview-mode) .pane-preview {
      display: none;
    }
    .panes.preview-mode .pane-editor {
      display: none;
    }
    .pane-preview {
      border: none;
    }
    .pane-properties {
      max-height: 42%;
      border-top: 1px solid var(--border);
    }
  }

  /* <768px: single column — the tab bar picks the visible pane */
  @media (max-width: 767px) {
    .panes {
      grid-template-columns: 1fr;
    }
    .panes .pane {
      display: none;
    }
    .panes[data-pane='editor'] .pane-editor,
    .panes[data-pane='preview'] .pane-preview,
    .panes[data-pane='properties'] .pane-properties {
      display: flex;
    }
    .pane-preview {
      border: none;
    }
    .pane-tabs {
      display: flex;
    }
    /* The tabs replace the toolbar preview toggle on mobile. */
    .preview-toggle {
      display: none;
    }
  }

  /* ≥1200px the live preview is a dedicated always-on pane — the toggle that
     swaps editor↔preview only makes sense below that breakpoint. */
  @media (min-width: 1200px) {
    .preview-toggle {
      display: none;
    }
  }
</style>
