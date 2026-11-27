<script lang="ts">
  import { SvelteDate } from 'svelte/reactivity';
  import { AlarmClock, Pencil, Trash2 } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { locale as localeStore } from '$lib/stores/locale';
  import { use24HourClock } from '$lib/stores/settings';
  import {
    alarmGroups,
    alarms,
    deleteAlarm,
    formatDurationShort,
    now,
    toggleAlarm,
    type Alarm,
  } from '$lib/stores/timers';

  let { onedit }: { onedit: (alarm: Alarm) => void } = $props();

  const DOW_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  const DAY_MS = 24 * 3600_000;

  function formatTime(a: Alarm): string {
    const d = new SvelteDate();
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

  /** "in 7h 23m" — or weekday + time once the fire date is beyond today
   *  (relative hour counts get unwieldy past ~24h). */
  function nextFireLabel(at: number): string {
    const delta = at - $now;
    if (delta < DAY_MS) {
      return $t('timers.alarm.nextIn', { values: { time: formatDurationShort(delta) } });
    }
    const d = new Date(at);
    const day = d.toLocaleDateString($localeStore, { weekday: 'short' });
    const time = d.toLocaleTimeString($localeStore, {
      hour: '2-digit',
      minute: '2-digit',
      hour12: !$use24HourClock,
    });
    return `${day} ${time}`;
  }
</script>

<div class="alarms-panel">
  {#if $alarms.length === 0}
    <div class="empty">
      <AlarmClock size={26} strokeWidth={1.5} />
      <p class="muted">{$t('timers.alarm.empty')}</p>
    </div>
  {:else}
    {#if $alarmGroups.upcoming.length > 0}
      <div class="group">
        <span class="group-label muted">{$t('timers.alarm.upcoming')}</span>
        <ul class="alarm-list">
          {#each $alarmGroups.upcoming as entry (entry.alarm.id)}
            {@const a = entry.alarm}
            <li class="alarm-row" class:snoozed={!!a.snoozedUntil}>
              <button
                type="button"
                class="alarm-main"
                onclick={() => onedit(a)}
                aria-label={$t('timers.alarm.edit')}
              >
                <span class="alarm-time mono">{formatTime(a)}</span>
                <span class="alarm-meta">
                  {#if a.label}<span class="alarm-label">{a.label}</span>{/if}
                  <span class="alarm-repeat muted">
                    {repeatSummary(a)}
                    {#if a.snoozedUntil}
                      · <span class="snooze-chip">{$t('timers.alert.snooze')}</span>
                    {/if}
                  </span>
                </span>
                <span class="next-fire mono">{nextFireLabel(entry.at)}</span>
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
                  onclick={() => onedit(a)}><Pencil size={14} /></button
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
      </div>
    {/if}

    {#if $alarmGroups.inactive.length > 0}
      <div class="group">
        <span class="group-label muted">{$t('timers.alarm.inactive')}</span>
        <ul class="alarm-list">
          {#each $alarmGroups.inactive as a (a.id)}
            <li class="alarm-row off">
              <button
                type="button"
                class="alarm-main"
                onclick={() => onedit(a)}
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
                  onclick={() => onedit(a)}><Pencil size={14} /></button
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
      </div>
    {/if}
  {/if}
</div>

<style>
  .alarms-panel {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-height: 80px;
  }
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s3);
    padding: var(--s6) var(--s4);
    color: var(--text-muted);
  }
  .group {
    display: flex;
    flex-direction: column;
    gap: var(--s1_5);
  }
  .group-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.07em;
  }
  .alarm-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
  }
  .alarm-row {
    display: flex;
    align-items: center;
    gap: var(--s2_5);
    padding: var(--s2) var(--s1);
    border-radius: var(--r);
    transition: background var(--t-fast);
  }
  .alarm-row:hover {
    background: var(--hover);
  }
  .alarm-row.off {
    opacity: 0.55;
  }
  .alarm-main {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: var(--s3);
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
    min-width: 0;
  }
  .alarm-time {
    font-size: 22px;
    font-weight: 600;
    color: var(--text-primary);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .alarm-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    flex: 1;
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
  .snooze-chip {
    color: var(--xp-2);
    font-weight: 600;
  }
  .next-fire {
    font-size: 11px;
    color: var(--xp-2);
    white-space: nowrap;
    margin-left: auto;
  }
  .alarm-actions {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
  }
  .btn-icon.danger:hover {
    color: var(--error);
  }

  /* Toggle switch */
  .switch {
    position: relative;
    display: inline-block;
    width: 36px;
    height: 20px;
    margin-right: var(--s1);
    flex-shrink: 0;
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
    border-radius: var(--r-full);
    background: var(--border);
    transition: background var(--t-fast);
    cursor: pointer;
  }
  .slider::before {
    content: '';
    position: absolute;
    width: 14px;
    height: 14px;
    left: 3px;
    top: 3px;
    border-radius: 50%;
    background: var(--text-primary);
    transition: transform var(--t-fast);
  }
  .switch input:checked + .slider {
    background: var(--xp);
  }
  .switch input:checked + .slider::before {
    transform: translateX(16px);
    background: var(--xp-contrast-text, var(--bg));
  }
  .switch input:focus-visible + .slider {
    outline: 2px solid var(--xp-2);
    outline-offset: 2px;
  }
  @media (prefers-reduced-motion: reduce) {
    .alarm-row,
    .slider,
    .slider::before {
      transition: none;
    }
  }
</style>
