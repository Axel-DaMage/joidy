<script lang="ts">
  import { untrack } from 'svelte';
  import { fade, scale } from 'svelte/transition';
  import { X } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { focusTrap } from '$lib/actions/focusTrap';
  import type { Alarm } from '$lib/stores/timers';
  import { ALARM_SOUNDS, type AlarmSoundId } from '$lib/utils/clockAlerts';
  import { use24HourClock } from '$lib/stores/settings';

  let {
    alarm = null,
    onsave,
    onclose,
  }: {
    alarm?: Alarm | null;
    onsave: (payload: Omit<Alarm, 'id'> & { id?: string }) => void;
    onclose: () => void;
  } = $props();

  // Monday-first order matching mobile clock apps.
  const DOW_ORDER = [1, 2, 3, 4, 5, 6, 0];
  const DOW_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  const SNOOZE_OPTIONS = [5, 10, 15];

  // The page remounts this modal per edit session ({#if editorOpen}), so the
  // form seeds from a one-time snapshot of the prop — live reactivity is
  // neither needed nor wanted here.
  const seed = untrack(() => alarm);

  let hour = $state(seed?.hour ?? 7);
  let minute = $state(seed?.minute ?? 0);
  let label = $state(seed?.label ?? '');
  let days = $state<number[]>(seed ? [...seed.days] : []);
  let snoozeMinutes = $state(seed?.snoozeMinutes ?? 10);
  let sound = $state<AlarmSoundId>(seed?.sound ?? 'beep');

  function toggleDay(d: number) {
    days = days.includes(d) ? days.filter((x) => x !== d) : [...days, d].sort();
  }

  function setPreset(preset: 'daily' | 'weekdays' | 'weekends') {
    if (preset === 'daily') days = [0, 1, 2, 3, 4, 5, 6];
    else if (preset === 'weekdays') days = [1, 2, 3, 4, 5];
    else days = [0, 6];
  }

  function clampHour() {
    const max = $use24HourClock ? 23 : 12;
    const min = $use24HourClock ? 0 : 1;
    if (!Number.isFinite(hour)) hour = 7;
    hour = Math.max(min, Math.min(max, Math.round(hour)));
  }
  function clampMinute() {
    if (!Number.isFinite(minute)) minute = 0;
    minute = Math.max(0, Math.min(59, Math.round(minute)));
  }

  function submit() {
    clampHour();
    clampMinute();
    onsave({
      id: alarm?.id,
      hour,
      minute,
      label: label.trim(),
      days,
      enabled: alarm?.enabled ?? true,
      snoozeMinutes,
      sound,
    });
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && (e.target as HTMLElement)?.tagName !== 'BUTTON') {
      e.preventDefault();
      submit();
    }
  }
</script>

<div class="modal-backdrop" role="presentation" transition:fade={{ duration: 120 }} onclick={onclose}>
  <div
    class="alarm-modal card"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    aria-label={$t('timers.alarm.editorTitle')}
    transition:scale={{ duration: 160, start: 0.95 }}
    use:focusTrap={{ onEscape: onclose }}
    onclick={(e) => e.stopPropagation()}
    onkeydown={onKeydown}
  >
    <div class="modal-head">
      <h3>{alarm ? $t('timers.alarm.edit') : $t('timers.alarm.new')}</h3>
      <button type="button" class="btn-icon" aria-label={$t('common.close')} onclick={onclose}>
        <X size={16} />
      </button>
    </div>

    <div class="time-picker">
      <input
        class="time-input mono"
        type="number"
        min={$use24HourClock ? 0 : 1}
        max={$use24HourClock ? 23 : 12}
        bind:value={hour}
        onblur={clampHour}
        aria-label={$t('timers.alarm.hour')}
      />
      <span class="time-sep mono">:</span>
      <input
        class="time-input mono"
        type="number"
        min="0"
        max="59"
        bind:value={minute}
        onblur={clampMinute}
        aria-label={$t('timers.alarm.minute')}
      />
    </div>

    <label class="field">
      <span class="label">{$t('timers.alarm.label')}</span>
      <input
        class="input"
        type="text"
        maxlength="80"
        placeholder={$t('timers.alarm.labelPlaceholder')}
        bind:value={label}
      />
    </label>

    <div class="field">
      <span class="label">{$t('timers.alarm.repeat')}</span>
      <div class="dow-row" role="group" aria-label={$t('timers.alarm.repeat')}>
        {#each DOW_ORDER as d (d)}
          <button
            type="button"
            class="dow-chip"
            class:on={days.includes(d)}
            aria-pressed={days.includes(d)}
            onclick={() => toggleDay(d)}>{$t(`timers.dow.${DOW_KEYS[d]}`)}</button
          >
        {/each}
      </div>
      <div class="preset-row">
        <button type="button" class="btn-ghost preset" onclick={() => (days = [])}
          >{$t('timers.repeat.once')}</button
        >
        <button type="button" class="btn-ghost preset" onclick={() => setPreset('daily')}
          >{$t('timers.repeat.daily')}</button
        >
        <button type="button" class="btn-ghost preset" onclick={() => setPreset('weekdays')}
          >{$t('timers.repeat.weekdays')}</button
        >
        <button type="button" class="btn-ghost preset" onclick={() => setPreset('weekends')}
          >{$t('timers.repeat.weekends')}</button
        >
      </div>
    </div>

    <div class="field-grid">
      <label class="field">
        <span class="label">{$t('timers.alarm.snooze')}</span>
        <select class="input" bind:value={snoozeMinutes}>
          {#each SNOOZE_OPTIONS as m (m)}
            <option value={m}>{$t('timers.alarm.snoozeMins', { values: { minutes: m } })}</option>
          {/each}
        </select>
      </label>
      <label class="field">
        <span class="label">{$t('timers.alarm.sound')}</span>
        <select class="input" bind:value={sound}>
          {#each ALARM_SOUNDS as s (s)}
            <option value={s}>{$t(`timers.sounds.${s}`)}</option>
          {/each}
        </select>
      </label>
    </div>

    <div class="modal-actions">
      <button type="button" class="btn btn-ghost" onclick={onclose}
        >{$t('common.cancel')}</button
      >
      <button type="button" class="btn btn-primary" onclick={submit}>{$t('common.save')}</button>
    </div>
  </div>
</div>

<style>
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: var(--z-modal);
    padding: var(--s4);
  }
  .alarm-modal {
    width: 100%;
    max-width: 380px;
    padding: var(--s4);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }
  .modal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .modal-head h3 {
    margin: 0;
    font-size: 15px;
  }
  .time-picker {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--s2);
  }
  .time-input {
    width: 88px;
    text-align: center;
    font-size: 40px;
    font-weight: 600;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-primary);
    padding: var(--s2) var(--s1);
  }
  .time-input:focus {
    outline: none;
    border-color: var(--xp-2);
  }
  .time-sep {
    font-size: 36px;
    font-weight: 600;
    color: var(--text-muted);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--s1_5);
  }
  .field-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s2_5);
  }
  .dow-row {
    display: flex;
    gap: var(--s1_5);
    flex-wrap: wrap;
  }
  .dow-chip {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 11px;
    cursor: pointer;
    transition:
      background var(--t-fast),
      border-color var(--t-fast),
      color var(--t-fast);
  }
  .dow-chip.on {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
    font-weight: 600;
  }
  .preset-row {
    display: flex;
    gap: var(--s1);
    flex-wrap: wrap;
  }
  .preset {
    font-size: 11px;
    padding: var(--s1) var(--s2_5);
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--s2);
  }
  @media (prefers-reduced-motion: reduce) {
    .dow-chip {
      transition: none;
    }
  }
</style>
