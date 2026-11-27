<script lang="ts">
  import { scale, fade } from 'svelte/transition';
  import { AlarmClock, BellRing, ClockPlus, RotateCcw, Timer, Plus } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { focusTrap } from '$lib/actions/focusTrap';
  import {
    activeAlert,
    addMinuteToTimer,
    alarms,
    dismissAlert,
    restartTimer,
    snoozeAlert,
  } from '$lib/stores/timers';

  const alert = $derived($activeAlert);
  const snoozeMinutes = $derived(
    alert?.kind === 'alarm'
      ? ($alarms.find((a) => a.id === alert.id)?.snoozeMinutes ?? 10)
      : null
  );

  function restart() {
    if (alert?.kind === 'timer') restartTimer(alert.id);
  }
  function plusOne() {
    if (alert?.kind === 'timer') {
      addMinuteToTimer(alert.id);
      dismissAlert();
    }
  }
</script>

{#if alert}
  <!-- Unmissable full-screen alert for firing alarms/timers (#1663). -->
  <div class="alert-overlay" transition:fade={{ duration: 120 }}>
    <div
      class="alert-card"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="clock-alert-title"
      tabindex="-1"
      transition:scale={{ duration: 160, start: 0.94 }}
      use:focusTrap={{ onEscape: dismissAlert }}
    >
      <div class="alert-icon" class:alarm={alert.kind === 'alarm'}>
        {#if alert.kind === 'alarm'}
          <AlarmClock size={30} strokeWidth={1.6} />
        {:else}
          <Timer size={30} strokeWidth={1.6} />
        {/if}
        <span class="alert-ring" aria-hidden="true"></span>
      </div>

      <h2 id="clock-alert-title">
        {alert.kind === 'alarm' ? $t('timers.alert.alarmTitle') : $t('timers.alert.timerTitle')}
      </h2>
      {#if alert.label}
        <p class="alert-label">{alert.label}</p>
      {/if}

      <div class="alert-actions">
        {#if alert.kind === 'alarm'}
          <button type="button" class="btn" onclick={snoozeAlert}>
            <ClockPlus size={14} />
            {$t('timers.alert.snooze')}
            {#if snoozeMinutes !== null}
              <span class="snooze-mins mono"
                >{$t('timers.alarm.snoozeMins', { values: { minutes: snoozeMinutes } })}</span
              >
            {/if}
          </button>
        {:else}
          <button type="button" class="btn" onclick={restart}>
            <RotateCcw size={14} />
            {$t('timers.alert.restart')}
          </button>
          <button type="button" class="btn" onclick={plusOne}>
            <Plus size={14} />
            {$t('timers.timer.plusOne')}
          </button>
        {/if}
        <button type="button" class="btn btn-primary" onclick={dismissAlert}>
          <BellRing size={14} />
          {$t('timers.alert.dismiss')}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .alert-overlay {
    position: fixed;
    inset: 0;
    z-index: var(--z-toast);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--s4);
    background: color-mix(in srgb, var(--bg) 72%, transparent);
    backdrop-filter: blur(6px);
  }
  .alert-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s3);
    width: 100%;
    max-width: 360px;
    padding: var(--s6) var(--s5);
    background: var(--surface);
    border: 1px solid var(--xp-2);
    border-radius: var(--r);
    text-align: center;
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);
  }
  .alert-icon {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 64px;
    height: 64px;
    color: var(--xp);
  }
  .alert-ring {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 1px solid var(--xp-2);
    animation: alertPulse 1.6s ease-out infinite;
  }
  @keyframes alertPulse {
    0% {
      transform: scale(0.7);
      opacity: 0.9;
    }
    100% {
      transform: scale(1.35);
      opacity: 0;
    }
  }
  .alert-card h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
  }
  .alert-label {
    margin: 0;
    font-size: 13px;
    color: var(--text-secondary);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .alert-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--s2);
    margin-top: var(--s2);
  }
  .snooze-mins {
    font-size: 11px;
    opacity: 0.75;
  }
  @media (prefers-reduced-motion: reduce) {
    .alert-ring {
      animation: none;
    }
  }
</style>
