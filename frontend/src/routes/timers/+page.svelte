<script lang="ts">
  import { onMount } from 'svelte';
  import { AlarmClock, Timer, Hourglass, Plus } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import AlarmsPanel from '$lib/components/timers/AlarmsPanel.svelte';
  import TimersPanel from '$lib/components/timers/TimersPanel.svelte';
  import StopwatchPanel from '$lib/components/timers/StopwatchPanel.svelte';
  import NextUpHero from '$lib/components/timers/NextUpHero.svelte';
  import AlarmEditorModal from '$lib/components/timers/AlarmEditorModal.svelte';
  import { initTimersEngine, saveAlarm, type Alarm } from '$lib/stores/timers';

  let editorOpen = $state(false);
  let editing = $state<Alarm | null>(null);

  function openNewAlarm() {
    editing = null;
    editorOpen = true;
  }
  function openEditAlarm(a: Alarm) {
    editing = a;
    editorOpen = true;
  }
  function onAlarmSave(payload: Omit<Alarm, 'id'> & { id?: string }) {
    saveAlarm(payload);
    editorOpen = false;
    editing = null;
  }

  onMount(() => {
    initTimersEngine();
  });
</script>

<svelte:head>
  <title>{$t('timers.pageTitle')}</title>
</svelte:head>

<div class="timers-page">
  <NextUpHero />

  <div class="dash-grid">
    <section
      class="panel card"
      id="timers-section-timers"
      aria-label={$t('timers.sections.timers')}
    >
      <header class="panel-head">
        <Timer size={15} strokeWidth={1.8} />
        <h2>{$t('timers.sections.timers')}</h2>
      </header>
      <TimersPanel />
    </section>

    <div class="side-col">
      <section
        class="panel card"
        id="timers-section-alarms"
        aria-label={$t('timers.sections.alarms')}
      >
        <header class="panel-head">
          <AlarmClock size={15} strokeWidth={1.8} />
          <h2>{$t('timers.sections.alarms')}</h2>
          <button type="button" class="btn btn-ghost head-action" onclick={openNewAlarm}>
            <Plus size={14} />
            {$t('timers.alarm.new')}
          </button>
        </header>
        <AlarmsPanel onedit={openEditAlarm} />
      </section>

      <section
        class="panel card"
        id="timers-section-stopwatch"
        aria-label={$t('timers.sections.stopwatch')}
      >
        <header class="panel-head">
          <Hourglass size={15} strokeWidth={1.8} />
          <h2>{$t('timers.sections.stopwatch')}</h2>
        </header>
        <StopwatchPanel />
      </section>
    </div>
  </div>
</div>

{#if editorOpen}
  <AlarmEditorModal
    alarm={editing}
    onsave={onAlarmSave}
    onclose={() => {
      editorOpen = false;
      editing = null;
    }}
  />
{/if}

<!-- The full-screen clock alert overlay is mounted globally in +layout so it
     stays unmissable on any route (#1663). -->

<style>
  .timers-page {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    padding: var(--s3);
    box-sizing: border-box;
    min-height: 100%;
  }
  .dash-grid {
    display: grid;
    grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
    gap: var(--s3);
    align-items: start;
  }
  .side-col {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-width: 0;
  }
  .panel {
    padding: var(--s3);
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    min-width: 0;
  }
  .panel-head {
    display: flex;
    align-items: center;
    gap: var(--s2);
    color: var(--text-secondary);
  }
  .panel-head h2 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: var(--text-primary);
  }
  .head-action {
    margin-left: auto;
    padding: var(--s1) var(--s2);
    font-size: 12px;
  }
  @media (max-width: 980px) {
    .dash-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
