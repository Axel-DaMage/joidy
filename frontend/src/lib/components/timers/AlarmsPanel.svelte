<script lang="ts">
  import { Plus, Pencil, Trash2, AlarmClock } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { locale as localeStore } from '$lib/stores/locale';
  import { use24HourClock } from '$lib/stores/settings';
  import { alarms, deleteAlarm, saveAlarm, toggleAlarm, type Alarm } from '$lib/stores/timers';
  import AlarmEditorModal from './AlarmEditorModal.svelte';

  const DOW_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

  let editorOpen = false;
  let editing: Alarm | null = null;

  function openNew() {
    editing = null;
    editorOpen = true;
  }
  function openEdit(a: Alarm) {
    editing = a;
    editorOpen = true;
  }
  function onSave(e: CustomEvent<Omit<Alarm, 'id'> & { id?: string }>) {
    saveAlarm(e.detail);
    editorOpen = false;
    editing = null;
  }

  function formatTime(a: Alarm): string {
    const d = new Date();
    d.setHours(a.hour, a.minute, 0, 0);
    return d.toLocaleTimeString($localeStore, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: !$use24HourClock,
    });
  }

  function repeatSummary(a: Alarm): string {
    const days = [...a.days].sort();
    if (days.length === 0) return $t('timers.repeat.once');
    if (days.length === 7) return $t('timers.repeat.daily');
    if (days.length === 5 && days.every((d) => d >= 1 && d <= 5))
      return $t('timers.repeat.weekdays');
    if (days.length === 2 && days.includes(0) && days.includes(6))
      return $t('timers.repeat.weekends');
    return days.map((d) => $t(`timers.dow.${DOW_KEYS[d]}`)).join(', ');
  }
</script>

<div class="alarms-panel">
  {#if $alarms.length === 0}
    <div class="empty card">
      <AlarmClock size={28} strokeWidth={1.5} />
      <p class="muted">{$t('timers.alarm.empty')}</p>
      <button type="button" class="btn btn-primary" onclick={openNew}>
        <Plus size={14} />
        {$t('timers.alarm.new')}
      </button>
    </div>
  {:else}
    <ul class="alarm-list">
      {#each $alarms as a (a.id)}
        <li class="alarm-row card" class:off={!a.enabled}>
          <button
            type="button"
            class="alarm-main"
            onclick={() => openEdit(a)}
            aria-label={$t('timers.alarm.edit')}
          >
            <span class="alarm-time mono">{formatTime(a)}</span>
            <span class="alarm-meta">
              {#if a.label}<span class="alarm-label">{a.label}</span>{/if}
              <span class="alarm-repeat muted">{repeatSummary(a)}</span>
            </span>
          </button>
          <div class="alarm-actions">
            <label class="switch" title={$t('timers.alarm.toggle')}>
              <input
                type="checkbox"
                checked={a.enabled}
                onchange={(e) => toggleAlarm(a.id, e.currentTarget.checked)}
                aria-label={$t('timers.alarm.toggle')}
              />
              <span class="slider"></span>
            </label>
            <button
              type="button"
              class="btn-icon"
              aria-label={$t('timers.alarm.edit')}
              onclick={() => openEdit(a)}><Pencil size={14} /></button
            >
            <button
              type="button"
              class="btn-icon danger"
              aria-label={$t('common.delete')}
              onclick={() => deleteAlarm(a.id)}><Trash2 size={14} /></button
            >
          </div>
        </li>
      {/each}
    </ul>
    <button
      type="button"
      class="fab btn-primary"
      onclick={openNew}
      aria-label={$t('timers.alarm.new')}
    >
      <Plus size={18} />
    </button>
  {/if}

  {#if editorOpen}
    <AlarmEditorModal
      alarm={editing}
      on:save={onSave}
      on:close={() => {
        editorOpen = false;
        editing = null;
      }}
    />
  {/if}
</div>

<style>
  .alarms-panel {
    position: relative;
    min-height: 200px;
  }
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 40px 20px;
    color: var(--text-muted);
  }
  .alarm-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .alarm-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    transition: opacity 0.15s;
  }
  .alarm-row.off {
    opacity: 0.55;
  }
  .alarm-main {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 14px;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
    min-width: 0;
  }
  .alarm-time {
    font-size: 28px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
  }
  .alarm-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .alarm-label {
    font-size: 12px;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .alarm-repeat {
    font-size: 11px;
  }
  .alarm-actions {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .btn-icon.danger:hover {
    color: var(--danger, #ef4444);
  }

  /* Toggle switch */
  .switch {
    position: relative;
    display: inline-block;
    width: 40px;
    height: 22px;
    margin-right: 4px;
  }
  .switch input {
    opacity: 0;
    width: 0;
    height: 0;
    position: absolute;
  }
  .slider {
    position: absolute;
    inset: 0;
    border-radius: 22px;
    background: var(--border);
    transition: background 0.15s;
    cursor: pointer;
  }
  .slider::before {
    content: '';
    position: absolute;
    width: 16px;
    height: 16px;
    left: 3px;
    top: 3px;
    border-radius: 50%;
    background: var(--text-primary);
    transition: transform 0.15s;
  }
  .switch input:checked + .slider {
    background: var(--accent);
  }
  .switch input:checked + .slider::before {
    transform: translateX(18px);
    background: var(--accent-contrast-text, #fff);
  }
  .switch input:focus-visible + .slider {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .fab {
    position: fixed;
    right: 24px;
    bottom: 88px;
    width: 48px;
    height: 48px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    z-index: 50;
  }
</style>
