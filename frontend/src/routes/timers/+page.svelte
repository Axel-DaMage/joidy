<script lang="ts">
  import { onMount } from 'svelte';
  import { AlarmClock, Timer, Hourglass, BellRing, ClockPlus } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import AlarmsPanel from '$lib/components/timers/AlarmsPanel.svelte';
  import TimersPanel from '$lib/components/timers/TimersPanel.svelte';
  import StopwatchPanel from '$lib/components/timers/StopwatchPanel.svelte';
  import { activeAlert, dismissAlert, initTimersEngine, snoozeAlert } from '$lib/stores/timers';

  type Tab = 'alarms' | 'timers' | 'stopwatch';
  let tab: Tab = 'alarms';

  const TABS: { id: Tab; key: string; icon: typeof AlarmClock }[] = [
    { id: 'alarms', key: 'timers.tabs.alarms', icon: AlarmClock },
    { id: 'timers', key: 'timers.tabs.timers', icon: Timer },
    { id: 'stopwatch', key: 'timers.tabs.stopwatch', icon: Hourglass },
  ];

  onMount(() => {
    initTimersEngine();
  });
</script>

<svelte:head>
  <title>{$t('timers.pageTitle')}</title>
</svelte:head>

<div class="timers-page">
  {#if $activeAlert}
    <div class="alert-banner" role="alert">
      <BellRing size={18} />
      <div class="alert-text">
        <strong>
          {$activeAlert.kind === 'alarm'
            ? $t('timers.alert.alarmTitle')
            : $t('timers.alert.timerTitle')}
        </strong>
        {#if $activeAlert.label}<span class="alert-label">{$activeAlert.label}</span>{/if}
      </div>
      <div class="alert-actions">
        {#if $activeAlert.kind === 'alarm'}
          <button type="button" class="btn btn-ghost" onclick={snoozeAlert}>
            <ClockPlus size={14} />
            {$t('timers.alert.snooze')}
          </button>
        {/if}
        <button type="button" class="btn btn-primary" onclick={dismissAlert}>
          {$t('timers.alert.dismiss')}
        </button>
      </div>
    </div>
  {/if}

  <div class="page-head">
    <div class="tabs" role="tablist" aria-label={$t('timers.title')}>
      {#each TABS as { id, key, icon }}
        <button
          type="button"
          role="tab"
          class="tab"
          class:active={tab === id}
          aria-selected={tab === id}
          onclick={() => (tab = id)}
        >
          <svelte:component this={icon} size={14} />
          <span>{$t(key)}</span>
        </button>
      {/each}
    </div>
  </div>

  <div class="tab-body" role="tabpanel">
    {#if tab === 'alarms'}
      <AlarmsPanel />
    {:else if tab === 'timers'}
      <TimersPanel />
    {:else}
      <StopwatchPanel />
    {/if}
  </div>
</div>

<style>
  .timers-page {
    max-width: 720px;
    margin: 0 auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    min-height: 100%;
  }
  .page-head {
    display: flex;
    justify-content: center;
  }
  .tabs {
    display: inline-flex;
    gap: 4px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 4px;
  }
  .tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    border-radius: 999px;
    border: none;
    background: transparent;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .tab.active {
    background: var(--accent);
    color: var(--accent-contrast-text, #fff);
    font-weight: 600;
  }
  .tab:not(.active):hover {
    color: var(--text-primary);
  }
  .alert-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--accent) 14%, var(--surface));
    border: 1px solid var(--accent);
    color: var(--text-primary);
    animation: alertPulse 1.4s ease-in-out infinite;
  }
  @keyframes alertPulse {
    0%,
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 35%, transparent);
    }
    50% {
      box-shadow: 0 0 0 8px transparent;
    }
  }
  .alert-text {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  .alert-label {
    font-size: 12px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .alert-actions {
    display: flex;
    gap: 8px;
  }
  .tab-body {
    flex: 1;
  }
</style>
