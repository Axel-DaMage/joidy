<script lang="ts">
  /**
   * Full event editor modal (#1658): Google-parity fields — title,
   * description, location, attendees, color — plus Joidy-native goal
   * linking, recurrence, reminders and vault-note quick-capture.
   *
   * Modes:
   *  - 'create' / 'edit-task'  → joidy task (optionally mirrored to Google)
   *  - 'edit-google'           → cached Google event patched via write-back
   */
  import type { CalendarEvent, CalendarTask, Goal } from '$lib/api';
  import type {
    CalendarTaskPriority,
    CalendarTaskRecurrence,
  } from '$lib/api';
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import Trash2 from 'lucide-svelte/icons/trash-2';
  import Copy from 'lucide-svelte/icons/copy';
  import NotebookPen from 'lucide-svelte/icons/notebook-pen';
  import ExternalLink from 'lucide-svelte/icons/external-link';
  import { t } from 'svelte-i18n';

  export interface EventEditorSave {
    title: string;
    date: string | null;
    start_time: string | null;
    end_time: string | null;
    priority: CalendarTaskPriority;
    recurrence: CalendarTaskRecurrence;
    reminder_minutes: number | null;
    color: string | null;
    description: string | null;
    location: string | null;
    attendees: string | null;
    goal_id: number | null;
    publishToGoogle: boolean;
  }

  export interface GoogleEventSave {
    summary: string;
    description: string | null;
    location: string | null;
  }

  let {
    open,
    mode,
    task = null,
    googleEvent = null,
    initialDate = null,
    initialTime = null,
    goals = [],
    connected = false,
    saving = false,
    onClose,
    onSaveTask,
    onSaveGoogle,
    onDelete,
    onDuplicate,
    onCreateNote,
  }: {
    open: boolean;
    mode: 'create' | 'edit-task' | 'edit-google';
    task?: CalendarTask | null;
    googleEvent?: CalendarEvent | null;
    initialDate?: string | null;
    initialTime?: string | null;
    goals?: Goal[];
    connected?: boolean;
    saving?: boolean;
    onClose: () => void;
    onSaveTask: (payload: EventEditorSave) => void;
    onSaveGoogle: (event: CalendarEvent, patch: GoogleEventSave) => void;
    onDelete?: (task: CalendarTask) => void;
    onDuplicate?: (task: CalendarTask) => void;
    onCreateNote?: (task: CalendarTask) => void;
  } = $props();

  const PRIORITIES: CalendarTaskPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'URGENT'];
  const RECURRENCE_OPTIONS: { value: CalendarTaskRecurrence; labelKey: string }[] = [
    { value: 'NONE', labelKey: 'recurrenceNone' },
    { value: 'DAILY', labelKey: 'recurrenceDaily' },
    { value: 'WEEKLY', labelKey: 'recurrenceWeekly' },
    { value: 'MONTHLY', labelKey: 'recurrenceMonthly' },
  ];
  const REMINDER_OPTIONS: { minutes: number | null; labelKey: string }[] = [
    { minutes: null, labelKey: 'reminderNone' },
    { minutes: 5, labelKey: 'reminderMin5' },
    { minutes: 15, labelKey: 'reminderMin15' },
    { minutes: 30, labelKey: 'reminderMin30' },
    { minutes: 60, labelKey: 'reminderMin60' },
  ];
  // Muted palette aligned with the app's tone (#1658).
  const COLOR_SWATCHES = [
    { value: null as string | null, label: 'default' },
    { value: '#c8a96e', label: 'gold' },
    { value: '#7ba3d4', label: 'blue' },
    { value: '#6fbf8f', label: 'green' },
    { value: '#d9534f', label: 'red' },
    { value: '#a97fd4', label: 'purple' },
    { value: '#e08c3a', label: 'orange' },
  ];

  let title = $state('');
  let date = $state<string>('');
  let startTime = $state('');
  let endTime = $state('');
  let priority = $state<CalendarTaskPriority>('MEDIUM');
  let recurrence = $state<CalendarTaskRecurrence>('NONE');
  let reminder = $state<number | null>(null);
  let color = $state<string | null>(null);
  let description = $state('');
  let location = $state('');
  let attendees = $state('');
  let goalId = $state<number | null>(null);
  let publishToGoogle = $state(false);
  let error = $state<string | null>(null);

  // Re-seed the form whenever the editor opens or the target changes.
  $effect(() => {
    if (!open) return;
    error = null;
    if (mode === 'edit-task' && task) {
      title = task.title;
      date = task.date ?? '';
      startTime = task.start_time?.slice(0, 5) ?? '';
      endTime = task.end_time?.slice(0, 5) ?? '';
      priority = task.priority;
      recurrence = task.recurrence;
      reminder = task.reminder_minutes;
      color = task.color;
      description = task.description ?? '';
      location = task.location ?? '';
      attendees = task.attendees ?? '';
      goalId = task.goal_id;
      publishToGoogle = false;
    } else if (mode === 'edit-google' && googleEvent) {
      title = googleEvent.summary ?? '';
      date = googleEvent.start_at.slice(0, 10);
      startTime = googleEvent.all_day ? '' : startTime;
      endTime = '';
      description = googleEvent.description ?? '';
      location = googleEvent.location ?? '';
      priority = 'MEDIUM';
      recurrence = 'NONE';
      reminder = null;
      color = null;
      attendees = '';
      goalId = null;
      publishToGoogle = false;
    } else {
      title = '';
      date = initialDate ?? '';
      startTime = initialTime?.slice(0, 5) ?? '';
      endTime = '';
      priority = 'MEDIUM';
      recurrence = 'NONE';
      reminder = null;
      color = null;
      description = '';
      location = '';
      attendees = '';
      goalId = null;
      publishToGoogle = false;
    }
  });

  function save(): void {
    const trimmed = title.trim();
    if (!trimmed) return;
    if (startTime && endTime && endTime <= startTime) {
      error = $t('calendar.endBeforeStart');
      return;
    }
    error = null;
    if (mode === 'edit-google' && googleEvent) {
      onSaveGoogle(googleEvent, {
        summary: trimmed,
        description: description.trim() || null,
        location: location.trim() || null,
      });
      return;
    }
    onSaveTask({
      title: trimmed,
      date: date || null,
      start_time: startTime ? `${startTime}:00` : null,
      end_time: endTime ? `${endTime}:00` : null,
      priority,
      recurrence,
      reminder_minutes: reminder,
      color,
      description: description.trim() || null,
      location: location.trim() || null,
      attendees: attendees.trim() || null,
      goal_id: goalId,
      publishToGoogle,
    });
  }

  const modalTitle = $derived(
    mode === 'create'
      ? $t('calendar.editor.newEvent')
      : mode === 'edit-google'
        ? $t('calendar.editor.editGoogle')
        : $t('calendar.editor.editEvent')
  );
</script>

<ModalDialog {open} title={modalTitle} size="md" onClose={onClose}>
  <form
    class="editor-form"
    onsubmit={(e) => {
      e.preventDefault();
      save();
    }}
  >
    <input
      class="input editor-title"
      type="text"
      bind:value={title}
      placeholder={$t('calendar.editor.titlePlaceholder')}
      aria-label={$t('calendar.editTitle')}
      maxlength="500"
      required
    />

    {#if mode !== 'edit-google'}
      <div class="editor-row">
        <label class="editor-field">
          <span class="caption">{$t('calendar.editor.date')}</span>
          <input class="input" type="date" bind:value={date} aria-label={$t('calendar.editor.date')} />
        </label>
        <label class="editor-field">
          <span class="caption">{$t('calendar.startTime')}</span>
          <input class="input" type="time" bind:value={startTime} aria-label={$t('calendar.startTime')} />
        </label>
        <label class="editor-field">
          <span class="caption">{$t('calendar.endTime')}</span>
          <input class="input" type="time" bind:value={endTime} aria-label={$t('calendar.endTime')} />
        </label>
      </div>
    {/if}

    <div class="editor-row">
      <label class="editor-field">
        <span class="caption">{$t('calendar.editor.location')}</span>
        <input
          class="input"
          type="text"
          bind:value={location}
          maxlength="500"
          placeholder={$t('calendar.editor.locationPlaceholder')}
        />
      </label>
    </div>

    <label class="editor-field">
      <span class="caption">{$t('calendar.editor.description')}</span>
      <textarea
        class="input editor-desc"
        bind:value={description}
        rows="3"
        maxlength="5000"
        placeholder={$t('calendar.editor.descriptionPlaceholder')}
      ></textarea>
    </label>

    {#if mode !== 'edit-google'}
      <div class="editor-row">
        <label class="editor-field">
          <span class="caption">{$t('calendar.priority')}</span>
          <select class="input" bind:value={priority}>
            {#each PRIORITIES as p}
              <option value={p}>{$t(`calendar.priorities.${p}`)}</option>
            {/each}
          </select>
        </label>
        <label class="editor-field">
          <span class="caption">{$t('calendar.recurrence')}</span>
          <select class="input" bind:value={recurrence}>
            {#each RECURRENCE_OPTIONS as opt (opt.labelKey)}
              <option value={opt.value}>{$t(`calendar.${opt.labelKey}`)}</option>
            {/each}
          </select>
        </label>
        <label class="editor-field">
          <span class="caption">{$t('calendar.reminder')}</span>
          <select class="input" bind:value={reminder}>
            {#each REMINDER_OPTIONS as opt (opt.labelKey)}
              <option value={opt.minutes}>{$t(`calendar.${opt.labelKey}`)}</option>
            {/each}
          </select>
        </label>
      </div>

      <div class="editor-row">
        <label class="editor-field grow">
          <span class="caption">{$t('calendar.editor.attendees')}</span>
          <input
            class="input"
            type="text"
            bind:value={attendees}
            maxlength="2000"
            placeholder={$t('calendar.editor.attendeesPlaceholder')}
          />
        </label>
        <label class="editor-field">
          <span class="caption">{$t('calendar.editor.goal')}</span>
          <select class="input" bind:value={goalId}>
            <option value={null}>{$t('calendar.editor.noGoal')}</option>
            {#each goals as goal (goal.id)}
              <option value={goal.id}>{goal.title}</option>
            {/each}
          </select>
        </label>
      </div>

      <div class="editor-row color-row">
        <span class="caption">{$t('calendar.editor.color')}</span>
        <div class="swatches" role="radiogroup" aria-label={$t('calendar.editor.color')}>
          {#each COLOR_SWATCHES as swatch}
            <button
              type="button"
              class="swatch"
              class:selected={color === swatch.value}
              style={swatch.value ? `background: ${swatch.value};` : ''}
              title={swatch.label}
              aria-label={swatch.label}
              aria-checked={color === swatch.value}
              role="radio"
              onclick={() => (color = swatch.value)}
            ></button>
          {/each}
        </div>
      </div>
    {/if}

    {#if error}<span class="editor-error caption">{error}</span>{/if}

    <div class="editor-footer">
      {#if mode === 'edit-task' && task}
        <div class="editor-secondary">
          {#if onCreateNote}
            <button
              type="button"
              class="btn btn-ghost editor-btn"
              onclick={() => onCreateNote(task)}
              title={$t('calendar.editor.createNoteHint')}
            >
              <NotebookPen size={12} />
              {task.note_id ? $t('calendar.editor.openNote') : $t('calendar.editor.createNote')}
            </button>
          {/if}
          {#if onDuplicate}
            <button
              type="button"
              class="btn btn-ghost editor-btn"
              onclick={() => onDuplicate(task)}
            >
              <Copy size={12} />
              {$t('calendar.editor.duplicate')}
            </button>
          {/if}
          {#if onDelete}
            <button
              type="button"
              class="btn btn-ghost editor-btn danger"
              onclick={() => onDelete(task)}
            >
              <Trash2 size={12} />
              {$t('calendar.delete')}
            </button>
          {/if}
        </div>
      {:else if mode === 'edit-google' && googleEvent?.html_link}
        <div class="editor-secondary">
          <a
            class="btn btn-ghost editor-btn"
            href={googleEvent.html_link}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ExternalLink size={12} />
            {$t('calendar.editor.openInGoogle')}
          </a>
        </div>
      {/if}
      {#if mode === 'create' && connected}
        <label class="publish-check" title={$t('calendar.publishToGoogleHint')}>
          <input type="checkbox" bind:checked={publishToGoogle} />
          <span>{$t('calendar.publishToGoogle')}</span>
        </label>
      {/if}
      <button type="submit" class="btn editor-save" disabled={saving || !title.trim()}>
        {saving ? $t('calendar.editor.saving') : $t('calendar.save')}
      </button>
    </div>
  </form>
</ModalDialog>

<style>
  .editor-form {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .editor-title {
    font-size: 15px;
    font-weight: 600;
  }

  .editor-row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
    flex-wrap: wrap;
  }

  .editor-field {
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
  }

  .editor-field.grow {
    flex: 1;
  }

  .editor-field .input {
    font-size: 12px;
    padding: var(--s2) var(--s2);
  }

  .editor-desc {
    resize: vertical;
    min-height: 56px;
    font-size: 12px;
  }

  .color-row {
    align-items: center;
    gap: 10px;
  }

  .swatches {
    display: flex;
    gap: 6px;
  }

  .swatch {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 2px solid transparent;
    background: var(--surface-2, rgba(255, 255, 255, 0.08));
    cursor: pointer;
    padding: 0;
  }

  .swatch.selected {
    border-color: var(--xp);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--xp) 35%, transparent);
  }

  .editor-error {
    color: var(--danger, #d9534f);
  }

  .editor-footer {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 4px;
    flex-wrap: wrap;
  }

  .editor-secondary {
    display: flex;
    gap: 4px;
    flex: 1;
    flex-wrap: wrap;
  }

  .editor-btn {
    font-size: 11px;
    padding: 4px 8px;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    text-decoration: none;
    color: inherit;
  }

  .editor-btn.danger:hover {
    color: var(--danger, #d9534f);
  }

  .publish-check {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 11px;
    color: var(--text-muted);
    cursor: pointer;
    margin-left: auto;
  }

  .editor-save {
    margin-left: auto;
  }

  .publish-check + .editor-save {
    margin-left: 0;
  }
</style>
