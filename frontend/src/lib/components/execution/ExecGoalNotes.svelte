<script lang="ts">
  import { goto } from '$app/navigation';
  import StickyNote from 'lucide-svelte/icons/sticky-note';
  import CalendarClock from 'lucide-svelte/icons/calendar-clock';
  import ChevronDown from 'lucide-svelte/icons/chevron-down';
  import Plus from 'lucide-svelte/icons/plus';
  import ExternalLink from 'lucide-svelte/icons/external-link';
  import { api, type Goal, type Note } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import { showNotification } from '$lib/stores/notifications';
  import { createNote, updateNote, deleteNote } from '$lib/stores/notes';
  import { ensureNoteEditor } from '$lib/utils/notesPage';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import {
    NoteEditorComp,
    NoteEditorError,
  } from '$lib/stores/notesUi';
  import type { ExecutionItem } from '$lib/utils/executionQueue';
  import { t } from 'svelte-i18n';

  /**
   * Execution-mode detail card for the hero item:
   *  - goal  → its linked follow-up note (`Goal.note_id`), editable inline so
   *            the user keeps capturing context without leaving the view.
   *    Creating the note also links it back to the goal; when the goal has a
   *    synced tag the note carries it so COUNT goals auto-track progress.
   *  - task  → compact read-only details (schedule, priority, recurrence).
   */

  let { item }: { item: ExecutionItem | null } = $props();

  let goal = $derived(item?.kind === 'goal' ? item.goal : null);
  let task = $derived(item?.kind === 'task' ? item.task : null);

  // ── Linked note state ──────────────────────────────────────────────────
  let note = $state<Note | null>(null);
  let noteLoading = $state(false);
  let creating = $state(false);
  let noteError = $state('');
  let tagsPromise: Promise<import('$lib/api').Tag[]> | null = null;

  // Editor body collapse — persisted like SacredCalendar's calendarId.
  let editorOpen = $state(loadUserSettings().executionUi?.notesExpanded !== false);
  function toggleEditor() {
    editorOpen = !editorOpen;
    patchUserSettings({ executionUi: { notesExpanded: editorOpen } });
  }

  function loadTags(): Promise<import('$lib/api').Tag[]> {
    tagsPromise ??= api.tags.list().catch((e) => {
      tagsPromise = null;
      throw e;
    });
    return tagsPromise;
  }

  // Resolve the goal's synced tag name (Goal.tag_id → Tag.name). Notes tagged
  // with that name count toward COUNT-goal progress (goal_service).
  async function goalTagNames(g: Goal): Promise<string[]> {
    if (g.tag_id == null) return [];
    try {
      const tags = await loadTags();
      const tag = tags.find((tg) => tg.id === g.tag_id);
      return tag ? [tag.name] : [];
    } catch (e) {
      logger.warn('[execution] tag lookup failed:', e);
      return [];
    }
  }

  $effect(() => {
    const g = goal;
    const key = item?.key;
    void key;
    if (!g) {
      note = null;
      noteLoading = false;
      noteError = '';
      return;
    }
    if (g.note_id == null) {
      note = null;
      noteLoading = false;
      noteError = '';
      return;
    }
    const noteId = g.note_id;
    noteLoading = true;
    noteError = '';
    api.notes
      .get(noteId)
      .then((n) => {
        // Stale-response guard: the hero may have changed while fetching.
        if (goal?.note_id === noteId) note = n;
      })
      .catch((e) => {
        logger.error('[execution] linked note fetch failed:', e);
        note = null;
        noteError = $t('executionPage.notesLoadError');
      })
      .finally(() => {
        noteLoading = false;
      });
  });

  async function createLinkedNote() {
    const g = goal;
    if (!g || creating) return;
    creating = true;
    noteError = '';
    try {
      const tags = await goalTagNames(g);
      const content = `# ${g.title}\n`;
      const created = await createNote(g.title, content, tags);
      if (!created) throw new Error('createNote returned null');
      await api.goals.update(g.id, { note_id: created.id });
      note = { ...created, content };
      showNotification($t('executionPage.noteCreated'), 'success');
    } catch (e) {
      logger.error('[execution] create linked note failed:', e);
      showNotification($t('executionPage.noteCreateError'), 'error');
    } finally {
      creating = false;
    }
  }

  async function handleEditorSave(e: CustomEvent<{ title: string; content: string; tags: string[] }>) {
    const current = note;
    if (!current) return;
    try {
      await updateNote(current.id, {
        title: e.detail.title,
        content: e.detail.content,
        tags: e.detail.tags,
      });
      note = { ...current, title: e.detail.title, content: e.detail.content, tags: e.detail.tags };
    } catch (err) {
      logger.error('[execution] note save failed:', err);
      showNotification($t('executionPage.noteSaveError'), 'error');
    }
  }

  async function reloadNote() {
    const current = note;
    if (!current) return;
    try {
      note = await api.notes.get(current.id);
    } catch (e) {
      logger.error('[execution] note reload failed:', e);
    }
  }

  async function handleEditorDelete() {
    const current = note;
    const g = goal;
    if (!current) return;
    try {
      await deleteNote(current.id);
      if (g) await api.goals.update(g.id, { note_id: null });
      note = null;
      showNotification($t('executionPage.noteDeleted'), 'info');
    } catch (e) {
      logger.error('[execution] note delete failed:', e);
      showNotification($t('executionPage.noteDeleteError'), 'error');
    }
  }

  function openInNotes() {
    if (note) void goto(`/notes?id=${note.id}`);
  }

  // Kick the shared lazy loader so the editor chunk is warm before the
  // user clicks "create" (same chunk the /notes page uses).
  $effect(() => {
    if (goal && goal.note_id != null) ensureNoteEditor();
  });
</script>

{#if goal}
  <section class="card exec-notes-card" aria-label={$t('executionPage.notesTitle')}>
    <header class="card-head">
      <StickyNote size={13} />
      <span class="card-title">{$t('executionPage.notesTitle')}</span>
      <button
        class="btn btn-ghost btn-icon collapse-btn"
        onclick={toggleEditor}
        title={editorOpen ? $t('executionPage.notesCollapse') : $t('executionPage.notesExpand')}
        aria-label={editorOpen ? $t('executionPage.notesCollapse') : $t('executionPage.notesExpand')}
        aria-expanded={editorOpen}
      >
        <ChevronDown size={13} class={editorOpen ? '' : 'rotated'} />
      </button>
      {#if note}
        <button
          class="btn btn-ghost btn-icon open-note"
          title={$t('executionPage.openInNotes')}
          aria-label={$t('executionPage.openInNotes')}
          onclick={openInNotes}
        >
          <ExternalLink size={12} />
        </button>
      {/if}
    </header>

    {#if goal.description}
      <p class="goal-desc">{goal.description}</p>
    {/if}

    <div class="goal-meta">
      <span class="meta-chip">{$t(`analyticsPage.goals.temporalities.${goal.temporality}`)}</span>
      <span class="meta-chip">
        {$t(`executionPage.measurement.${goal.measurement_type}`)}
      </span>
      {#if goal.state !== 'ACTIVE'}
        <span class="meta-chip muted-chip">{goal.state}</span>
      {/if}
    </div>

    {#if editorOpen}
      {#if noteError}
        <div class="error-banner">{noteError}</div>
      {/if}

      {#if noteLoading}
        <div class="notes-status caption">{$t('executionPage.notesLoading')}</div>
      {:else if note}
        <div class="note-editor-wrap">
          {#if $NoteEditorComp}
            {#key note.id}
              {@const Editor = $NoteEditorComp}
              <Editor
                {note}
                on:save={handleEditorSave}
                on:cancel={reloadNote}
                on:delete={handleEditorDelete}
              />
            {/key}
          {:else if $NoteEditorError}
            <div class="notes-status caption">
              <span>{$t('common.loadFailed')}</span>
              <button class="btn btn-ghost" onclick={() => ensureNoteEditor()}
                >{$t('common.retry')}</button
              >
            </div>
          {:else}
            <div class="notes-status caption">{$t('notesPage.editorLoading')}</div>
          {/if}
        </div>
      {:else}
        <div class="notes-empty">
          <p class="notes-empty-hint">{$t('executionPage.notesEmptyHint')}</p>
          <button class="btn" onclick={createLinkedNote} disabled={creating}>
            <Plus size={13} />
            {creating ? $t('executionPage.noteCreating') : $t('executionPage.noteCreate')}
          </button>
        </div>
      {/if}
    {/if}
  </section>
{:else if task}
  <section class="card exec-task-card" aria-label={$t('executionPage.taskDetails')}>
    <header class="card-head">
      <CalendarClock size={13} />
      <span class="card-title">{$t('executionPage.taskDetails')}</span>
    </header>

    <dl class="task-details">
      {#if task.date}
        <div class="td-row">
          <dt>{$t('executionPage.taskDate')}</dt>
          <dd class="mono">{task.date}</dd>
        </div>
      {/if}
      {#if task.start_time || task.end_time}
        <div class="td-row">
          <dt>{$t('executionPage.taskTime')}</dt>
          <dd class="mono">
            {task.start_time?.slice(0, 5) ?? '—'}{task.end_time ? ` → ${task.end_time.slice(0, 5)}` : ''}
          </dd>
        </div>
      {/if}
      <div class="td-row">
        <dt>{$t('executionPage.taskPriority')}</dt>
        <dd>{$t(`executionPage.prio.${task.priority.toLowerCase()}`)}</dd>
      </div>
      {#if task.recurrence && task.recurrence !== 'NONE'}
        <div class="td-row">
          <dt>{$t('calendar.recurrence')}</dt>
          <dd>{$t(`calendar.recurrence${task.recurrence === 'DAILY' ? 'Daily' : task.recurrence === 'WEEKLY' ? 'Weekly' : 'Monthly'}`)}</dd>
        </div>
      {/if}
      {#if task.reminder_minutes != null}
        <div class="td-row">
          <dt>{$t('executionPage.taskReminder')}</dt>
          <dd>{$t('executionPage.taskReminderMin', { values: { minutes: task.reminder_minutes } })}</dd>
        </div>
      {/if}
      <div class="td-row">
        <dt>{$t('executionPage.taskSource')}</dt>
        <dd>{task.source === 'GOOGLE' ? 'Google Calendar' : 'Joidy'}</dd>
      </div>
    </dl>
  </section>
{/if}

<style>
  .exec-notes-card,
  .exec-task-card {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    padding: var(--s3) var(--s4) var(--s4);
  }

  .card-head {
    display: flex;
    align-items: center;
    gap: var(--s2);
    color: var(--text-muted);
  }

  .card-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-secondary);
  }

  .open-note,
  .collapse-btn {
    margin-left: auto;
    width: 24px;
    height: 24px;
    color: var(--text-muted);
  }
  .collapse-btn + .open-note {
    margin-left: 0;
  }
  .open-note:hover,
  .collapse-btn:hover {
    color: var(--text-primary);
  }

  .collapse-btn :global(svg),
  .collapse-btn :global(.rotated) {
    transition: transform var(--t-fast);
  }
  .collapse-btn :global(.rotated) {
    transform: rotate(-90deg);
  }

  .goal-desc {
    margin: 0;
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
    display: -webkit-box;
    line-clamp: 3;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .goal-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1);
  }

  .meta-chip {
    font-size: 10px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .muted-chip {
    opacity: 0.7;
  }

  .error-banner {
    padding: var(--s2) var(--s3);
    border: 1px solid color-mix(in srgb, #d9534f 50%, var(--border));
    background: color-mix(in srgb, #d9534f 12%, transparent);
    color: #d9534f;
    border-radius: var(--r);
    font-size: 12px;
  }

  .notes-status {
    display: flex;
    align-items: center;
    gap: var(--s2);
    color: var(--text-muted);
    padding: var(--s2) 0;
  }

  .note-editor-wrap {
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
    background: var(--surface);
  }

  .notes-empty {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--s2);
    padding: var(--s2) 0;
  }

  .notes-empty-hint {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
  }

  .notes-empty .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--s1_5);
    font-size: 12px;
  }

  /* ── Task details ────────────────────────────────────────────────────── */
  .task-details {
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s1_5);
  }

  .td-row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--s3);
    font-size: 12px;
  }

  .td-row dt {
    color: var(--text-muted);
    font-size: 11px;
  }

  .td-row dd {
    margin: 0;
    color: var(--text-primary);
    text-align: right;
  }
</style>
