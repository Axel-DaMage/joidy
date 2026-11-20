<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { X } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { focusTrap } from '$lib/actions/focusTrap';
  import type { Alarm } from '$lib/stores/timers';
  import { ALARM_SOUNDS, type AlarmSoundId } from '$lib/utils/clockAlerts';
  import { use24HourClock } from '$lib/stores/settings';

  export let alarm: Alarm | null = null; // null = create new

  const dispatch = createEventDispatcher<{
    save: Omit<Alarm, 'id'> & { id?: string };
    close: void;
  }>();

  // Monday-first order matching mobile clock apps.
  const DOW_ORDER = [1, 2, 3, 4, 5, 6, 0];
  const DOW_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  const SNOOZE_OPTIONS = [5, 10, 15];

  let hour = alarm?.hour ?? 7;
  let minute = alarm?.minute ?? 0;
  let label = alarm?.label ?? '';
  let days: number[] = alarm ? [...alarm.days] : [];
  let snoozeMinutes = alarm?.snoozeMinutes ?? 10;
  let sound: AlarmSoundId = alarm?.sound ?? 'beep';

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
    dispatch('save', {
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

<div class="modal-backdrop" role="presentation" onclick={() => dispatch('close')}>
  <div
    class="alarm-modal card"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    aria-label={$t('timers.alarm.editorTitle')}
    use:focusTrap={{ onEscape: () => dispatch('close') }}
    onclick={(e) => e.stopPropagation()}
    onkeydown={onKeydown}
  >
    <div class="modal-head">
      <h3>{alarm ? $t('timers.alarm.edit') : $t('timers.alarm.new')}</h3>
      <button
        type="button"
        class="btn-icon"
        aria-label={$t('common.close')}
        onclick={() => dispatch('close')}
      >
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
        {#each DOW_ORDER as d}
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
          {#each SNOOZE_OPTIONS as m}
            <option value={m}>{$t('timers.alarm.snoozeMins', { values: { minutes: m } })}</option>
          {/each}
        </select>
      </label>
      <label class="field">
        <span class="label">{$t('timers.alarm.sound')}</span>
        <select class="input" bind:value={sound}>
          {#each ALARM_SOUNDS as s}
            <option value={s}>{$t(`timers.sounds.${s}`)}</option>
          {/each}
        </select>
      </label>
    </div>

    <div class="modal-actions">
      <button type="button" class="btn btn-ghost" onclick={() => dispatch('close')}
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
    z-index: 100;
    padding: 16px;
  }
  .alarm-modal {
    width: 100%;
    max-width: 380px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
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
    gap: 8px;
  }
  .time-input {
    width: 88px;
    text-align: center;
    font-size: 40px;
    font-weight: 600;
    background: var(--surface-2, var(--surface));
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-primary);
    padding: 8px 4px;
  }
  .time-input:focus {
    outline: none;
    border-color: var(--accent);
  }
  .time-sep {
    font-size: 36px;
    font-weight: 600;
    color: var(--text-muted);
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .field-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }
  .dow-row {
    display: flex;
    gap: 6px;
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
    transition: all 0.15s;
  }
  .dow-chip.on {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-contrast-text, #fff);
    font-weight: 600;
  }
  .preset-row {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .preset {
    font-size: 11px;
    padding: 4px 10px;
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
