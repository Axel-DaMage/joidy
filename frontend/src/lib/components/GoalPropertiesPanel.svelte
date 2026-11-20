<script lang="ts">
  // Properties pane for the Goal Editor (#935): deadline, priority, milestones
  // and linked notes. Every field persists immediately through the goals API —
  // the same pattern the context chips already used — and the updated goal is
  // written back to the shared `goalEditor` store plus reported to the
  // container via `onUpdate` so the page can merge it into its own state.
  import { api, type Goal, type Note, type Tag } from '$lib/api';
  import { t } from 'svelte-i18n';
  import { logger } from '$lib/utils/logger';
  import { goalEditor } from '$lib/stores/goalEditor.svelte';
  import NoteLinkPicker from './NoteLinkPicker.svelte';

  interface Props {
    notes?: Note[];
    tags?: Tag[];
    /** Called with the server-updated goal after every persisted change. */
    onUpdate?: (goal: Goal) => void;
    /** Create a new note and return it so it can be linked immediately. */
    onCreateNote?: (title: string) => void | Note | Promise<void | Note>;
  }

  let { notes = [], tags = [], onUpdate, onCreateNote }: Props = $props();

  // Tracks in-flight property saves so the panel can show a subtle indicator
  // without blocking further edits (last write wins, like the context chips).
  let updatingCount = $state(0);
  let updating = $derived(updatingCount > 0);

  async function updateGoal(patch: Partial<Goal>) {
    const current = goalEditor.goal;
    if (!current) return;
    updatingCount++;
    try {
      const updated = await api.goals.update(current.id, patch);
      goalEditor.goal = updated;
      onUpdate?.(updated);
    } catch (e) {
      logger.error('[GoalPropertiesPanel] update failed:', e);
    } finally {
      updatingCount--;
    }
  }

  // Local mirrors of editable fields — synced from the store whenever the
  // goal object changes, committed back to the API on change/blur.
  let editPriority = $state(0);
  let editLimitDays = $state<number | null>(null);
  let editMeasurement = $state<Goal['measurement_type']>('COUNT');
  let editTarget = $state(1);
  let linkedNoteId = $state<number | null>(null);
  let linkedTagId = $state<number | null>(null);

  $effect(() => {
    const g = goalEditor.goal;
    editPriority = g?.priority ?? 0;
    editLimitDays = g?.max_assignment_days ?? null;
    editMeasurement = g?.measurement_type ?? 'COUNT';
    editTarget = g?.target_value ?? 1;
    linkedNoteId = g?.note_id ?? null;
    linkedTagId = g?.tag_id ?? null;
  });

  // NoteLinkPicker only exposes bind:value, so link changes are detected by
  // diffing the local mirror against the stored goal and persisting the delta.
  $effect(() => {
    const value = linkedNoteId;
    const current = goalEditor.goal?.note_id ?? null;
    if (value !== current) void updateGoal({ note_id: value });
  });

  function commitLimitDays() {
    const v = editLimitDays;
    void updateGoal({ max_assignment_days: v && v > 0 ? Math.floor(v) : null });
  }

  function commitTarget() {
    const v = editTarget;
    void updateGoal({ target_value: v && v > 0 ? v : 1 });
  }

  async function handleCreateNote(title: string) {
    if (!onCreateNote) return;
    const created = await onCreateNote(title);
    if (created && typeof created === 'object' && 'id' in created) {
      linkedNoteId = created.id;
    }
  }

  const MILESTONE_STEPS = [25, 50, 75, 100];

  let goal = $derived(goalEditor.goal);
  let progressPct = $derived(Math.max(0, Math.min(100, Math.round(goal?.progress_pct ?? 0))));
  let currentValue = $derived(goal?.current_value ?? 0);
  let targetValue = $derived(goal?.target_value ?? 1);

  function formatDate(iso: string | null | undefined): string {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString();
    } catch {
      return iso;
    }
  }
</script>

<div class="properties-panel">
  <div class="panel-header">
    <span class="panel-title">{$t('goalEditor.properties')}</span>
    <span class="panel-status" role="status" aria-live="polite">
      {#if updating}{$t('goalEditor.savingProps')}{/if}
    </span>
  </div>

  {#if !goal}
    <p class="panel-empty">{$t('goalEditor.propertiesEmpty')}</p>
  {:else}
    <div class="panel-body" aria-busy={updating}>
      <!-- Deadline -->
      <section class="prop-section" aria-labelledby="goal-prop-deadline-h">
        <h4 id="goal-prop-deadline-h" class="prop-heading">{$t('goalEditor.deadline')}</h4>
        <div class="form-field">
          <label for="goal-prop-limit" class="label">{$t('goalDetail.limitDays')}</label>
          <input
            id="goal-prop-limit"
            class="input"
            type="number"
            min="1"
            bind:value={editLimitDays}
            onchange={commitLimitDays}
            placeholder={$t('goalDetail.unlimited')}
            disabled={updating}
          />
        </div>
        <dl class="meta-dates">
          <div class="meta-row">
            <dt>{$t('goalEditor.created')}</dt>
            <dd>{formatDate(goal.created_at)}</dd>
          </div>
          <div class="meta-row">
            <dt>{$t('goalEditor.completedAt')}</dt>
            <dd>{formatDate(goal.completed_at)}</dd>
          </div>
        </dl>
      </section>

      <!-- Priority -->
      <section class="prop-section" aria-labelledby="goal-prop-priority-h">
        <h4 id="goal-prop-priority-h" class="prop-heading">{$t('goalDetail.priority')}</h4>
        <div class="form-field">
          <label for="goal-prop-priority" class="label">{$t('goalDetail.priority')}</label>
          <select
            id="goal-prop-priority"
            class="input"
            bind:value={editPriority}
            onchange={() => updateGoal({ priority: editPriority })}
            disabled={updating}
          >
            {#each [0, 1, 2, 3, 4, 5] as p}
              <option value={p}
                >{p === 0
                  ? $t('goalDetail.priorityNone')
                  : $t('goalDetail.priorityLevel', { values: { level: p } })}</option
              >
            {/each}
          </select>
        </div>
      </section>

      <!-- Milestones -->
      <section class="prop-section" aria-labelledby="goal-prop-milestones-h">
        <h4 id="goal-prop-milestones-h" class="prop-heading">{$t('goalEditor.milestones')}</h4>
        <div
          class="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progressPct}
          aria-label={$t('goalEditor.progress')}
        >
          <div
            class="progress-fill"
            style="width: {progressPct}%; background: {goal.color || 'var(--accent)'};"
          ></div>
          {#each MILESTONE_STEPS as step}
            <span
              class="milestone-dot"
              class:reached={progressPct >= step}
              style="left: {step}%;"
              aria-hidden="true"
            ></span>
          {/each}
        </div>
        <div class="progress-meta">
          <span class="progress-value">{currentValue} / {targetValue}</span>
          <span class="progress-pct">{progressPct}%</span>
        </div>
        <div class="form-row">
          <div class="form-field" style="flex:1;">
            <label for="goal-prop-measurement" class="label"
              >{$t('goalDetail.measurementType')}</label
            >
            <select
              id="goal-prop-measurement"
              class="input"
              bind:value={editMeasurement}
              onchange={() => updateGoal({ measurement_type: editMeasurement })}
              disabled={updating}
            >
              <option value="COUNT">{$t('goalDetail.countNumeric')}</option>
              <option value="BOOLEAN">{$t('goalDetail.booleanDone')}</option>
              <option value="PERCENT">{$t('goalDetail.percent')}</option>
            </select>
          </div>
          <div class="form-field" style="width: 110px;">
            <label for="goal-prop-target" class="label">{$t('goalDetail.target')}</label>
            <input
              id="goal-prop-target"
              class="input"
              type="number"
              min="1"
              bind:value={editTarget}
              onchange={commitTarget}
              disabled={editMeasurement === 'BOOLEAN' || updating}
            />
          </div>
        </div>
      </section>

      <!-- Linked note + tag sync -->
      <section class="prop-section" aria-labelledby="goal-prop-links-h">
        <h4 id="goal-prop-links-h" class="prop-heading">{$t('goalEditor.linkedNotes')}</h4>
        <div class="form-field">
          <label for="goal-prop-note" class="label">{$t('goalDetail.linkToProject')}</label>
          <NoteLinkPicker
            {notes}
            bind:value={linkedNoteId}
            id="goal-prop-note"
            placeholder={$t('goalDetail.searchNote')}
            onCreateNote={handleCreateNote}
          />
        </div>
        <div class="form-field">
          <label for="goal-prop-tag" class="label">{$t('goalDetail.tagSync')}</label>
          <select
            id="goal-prop-tag"
            class="input"
            bind:value={linkedTagId}
            onchange={() => updateGoal({ tag_id: linkedTagId })}
            disabled={updating}
          >
            <option value={null}>{$t('goalDetail.manualUpdate')}</option>
            {#each notes as n}
              {@const tagId = tags.find((tg) => tg.name === n.title)?.id}
              {#if tagId}
                <option value={tagId}>{n.title} ({$t('goalEditor.autoTracking')})</option>
              {/if}
            {/each}
          </select>
        </div>
      </section>
    </div>
  {/if}
</div>

<style>
  .properties-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: var(--surface);
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .panel-title {
    font-size: 11px;
    font-family: var(--font-mono);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
  }

  .panel-status {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--accent);
    min-height: 12px;
  }

  .panel-empty {
    padding: 16px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .panel-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 12px 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .prop-section {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .prop-heading {
    font-size: 10px;
    font-family: var(--font-mono);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    padding-bottom: 5px;
    border-bottom: 1px solid var(--border-light, var(--border));
    margin: 0;
  }

  .label {
    display: block;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 6px;
  }

  .form-field {
    display: flex;
    flex-direction: column;
  }

  .form-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }

  .input {
    width: 100%;
    padding: 6px 8px;
    font-size: 12px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    background: var(--surface-hover);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }

  .input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 1px;
  }

  .input:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .meta-dates {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin: 0;
  }

  .meta-row {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }

  .meta-row dd {
    margin: 0;
  }

  .progress-track {
    position: relative;
    height: 8px;
    border-radius: 4px;
    background: var(--surface-hover);
    border: 1px solid var(--border);
    overflow: visible;
  }

  .progress-fill {
    height: 100%;
    border-radius: 4px;
    transition: width var(--t-fast, 0.2s);
  }

  .milestone-dot {
    position: absolute;
    top: 50%;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    background: var(--surface);
    border: 1px solid var(--border);
  }

  .milestone-dot.reached {
    background: var(--accent);
    border-color: var(--accent);
  }

  .progress-meta {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }

  .progress-pct {
    color: var(--text-muted);
  }
</style>
