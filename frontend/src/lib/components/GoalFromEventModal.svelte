<script lang="ts">
  // Quick goal creation seeded from a Google Calendar event. Two steps:
  // confirm → pre-filled compact form → create + Planning assignment on the
  // event's day (no calendar-task mirror — the Google event is already the
  // calendar entry; a mirror would publish a duplicate all-day event).
  import { t } from 'svelte-i18n';
  import Target from 'lucide-svelte/icons/target';
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import { api, type Goal } from '$lib/api';
  import { showNotification } from '$lib/stores/notifications';
  import { locale } from '$lib/stores/locale';
  import { DEFAULT_GOAL_COLOR } from '$lib/utils/goalColors';

  export interface GoalEventSeed {
    title: string;
    description?: string | null;
    location?: string | null;
    /** Effective event color (#rrggbb) — reused as the goal color when set. */
    color?: string | null;
    /** YYYY-MM-DD — Planning assignment anchor. */
    day: string;
  }

  let {
    event,
    onClose,
    onCreated,
  }: {
    event: GoalEventSeed;
    onClose: () => void;
    onCreated?: (goal: Goal) => void;
  } = $props();

  type Step = 'confirm' | 'form';
  let step = $state<Step>('confirm');
  let saving = $state(false);
  let failed = $state(false);

  let fTitle = $state('');
  let fDescription = $state('');
  let fTemporality = $state<Goal['temporality']>('ONEOFF');
  let fMeasurement = $state<Goal['measurement_type']>('BOOLEAN');
  let fTarget = $state(1);
  let fColor = $state(DEFAULT_GOAL_COLOR);

  const TEMPORALITIES: Goal['temporality'][] = ['ONEOFF', 'DAILY', 'WEEKLY', 'MONTHLY', 'ANNUAL'];
  const MEASUREMENTS: Goal['measurement_type'][] = ['BOOLEAN', 'COUNT', 'PERCENT'];

  const eventDayLabel = $derived(
    new Date(`${event.day}T12:00:00`).toLocaleDateString($locale, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    })
  );

  // Seed the editable fields from the event once per mount — the parent
  // mounts this component fresh for each event, so no reset logic needed.
  $effect(() => {
    fTitle = event.title;
    fDescription = [event.description, event.location ? `📍 ${event.location}` : null]
      .filter(Boolean)
      .join('\n\n');
    fColor = event.color ?? DEFAULT_GOAL_COLOR;
  });

  async function submit(): Promise<void> {
    if (!fTitle.trim() || saving) return;
    saving = true;
    failed = false;
    try {
      const goal = await api.goals.create({
        title: fTitle.trim(),
        description: fDescription.trim(),
        temporality: fTemporality,
        measurement_type: fMeasurement,
        target_value: fTarget,
        color: fColor || undefined,
      });
      // Link the goal to the event's day in Planning. create_calendar_task
      // stays false: the Google event is already the calendar entry.
      await api.planning.setAssignments(event.day, [goal.id], false);
      showNotification($t('goalFromEvent.created'), 'success');
      onCreated?.(goal);
      onClose();
    } catch {
      failed = true;
    } finally {
      saving = false;
    }
  }
</script>

<ModalDialog
  open={true}
  title={step === 'confirm' ? $t('goalFromEvent.confirmTitle') : $t('goalFromEvent.title')}
  size={step === 'form' ? 'md' : 'sm'}
  onClose={onClose}
>
  {#if step === 'confirm'}
    <p class="gfe-confirm">
      {$t('goalFromEvent.confirm', { values: { title: event.title, date: eventDayLabel } })}
    </p>
    <p class="gfe-hint caption">{$t('goalFromEvent.confirmHint')}</p>
  {:else}
    <div class="gfe-form">
      <label class="gfe-field">
        <span class="caption">{$t('goalFromEvent.goalTitle')}</span>
        <input class="input" type="text" bind:value={fTitle} maxlength="500" />
      </label>
      <label class="gfe-field">
        <span class="caption">{$t('goalFromEvent.description')}</span>
        <textarea class="input" rows="3" bind:value={fDescription}></textarea>
      </label>
      <div class="gfe-row">
        <label class="gfe-field">
          <span class="caption">{$t('goalFromEvent.temporalityLabel')}</span>
          <select class="input" bind:value={fTemporality}>
            {#each TEMPORALITIES as temp (temp)}
              <option value={temp}>{$t(`goalFromEvent.temporality.${temp}`)}</option>
            {/each}
          </select>
        </label>
        <label class="gfe-field">
          <span class="caption">{$t('goalFromEvent.measurementLabel')}</span>
          <select class="input" bind:value={fMeasurement}>
            {#each MEASUREMENTS as m (m)}
              <option value={m}>{$t(`goalFromEvent.measurement.${m}`)}</option>
            {/each}
          </select>
        </label>
        <label class="gfe-field gfe-target">
          <span class="caption">{$t('goalFromEvent.targetValue')}</span>
          <input class="input" type="number" min="1" bind:value={fTarget} />
        </label>
      </div>
      <label class="gfe-field">
        <span class="caption">{$t('goalFromEvent.color')}</span>
        <input class="input gfe-color" type="color" bind:value={fColor} />
      </label>
      {#if failed}
        <p class="gfe-error caption">{$t('goalFromEvent.error')}</p>
      {/if}
    </div>
  {/if}
  {#snippet footer()}
    {#if step === 'confirm'}
      <button type="button" class="btn btn-ghost" onclick={onClose}>
        {$t('goalFromEvent.cancel')}
      </button>
      <button type="button" class="btn btn-primary" onclick={() => (step = 'form')}>
        <Target size={14} /> {$t('goalFromEvent.action')}
      </button>
    {:else}
      <button type="button" class="btn btn-ghost" onclick={() => (step = 'confirm')}>
        {$t('goalFromEvent.back')}
      </button>
      <button
        type="button"
        class="btn btn-primary"
        disabled={saving || !fTitle.trim()}
        onclick={submit}
      >
        <Target size={14} /> {$t('goalFromEvent.create')}
      </button>
    {/if}
  {/snippet}
</ModalDialog>

<style>
  .gfe-confirm {
    margin: 0 0 var(--s2);
    font-size: var(--fs-sm);
  }
  .gfe-hint {
    margin: 0;
    color: var(--text-muted);
  }
  .gfe-form {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }
  .gfe-field {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .gfe-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
  }
  .gfe-row .gfe-field {
    flex: 1 1 140px;
    min-width: 0;
  }
  .gfe-target {
    flex: 0 0 90px;
  }
  .gfe-color {
    height: 36px;
    padding: 2px;
    cursor: pointer;
  }
  .gfe-error {
    margin: 0;
    color: var(--error, #d9534f);
  }
</style>
