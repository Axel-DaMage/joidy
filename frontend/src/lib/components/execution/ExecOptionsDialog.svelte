<script lang="ts">
  import ModalDialog from '$lib/components/ModalDialog.svelte';
  import TimerIcon from 'lucide-svelte/icons/timer';
  import Crosshair from 'lucide-svelte/icons/crosshair';
  import PanelsTopLeft from 'lucide-svelte/icons/panels-top-left';
  import { workMins, breakMins, running as pomRunning } from '$lib/stores/pomodoro';
  import { config as focusConfig, updateConfig } from '$lib/stores/focusMode';
  import { t } from 'svelte-i18n';

  /**
   * Execution-mode options dialog — mirrors the global settings row pattern
   * (.section/.row/.toggle/.setting-input) scoped to this view:
   * pomodoro durations, focus-mode config and rail visibility toggles.
   */

  let {
    open = $bindable(false),
    onClose,
    showQueue = $bindable(true),
    showCalendar = $bindable(true),
    showNotes = $bindable(true),
  }: {
    open?: boolean;
    onClose?: () => void;
    showQueue?: boolean;
    showCalendar?: boolean;
    showNotes?: boolean;
  } = $props();

  let fDur = $state(25);
  let fBrk = $state(5);
  let fCyc = $state(4);
  $effect(() => {
    const c = $focusConfig;
    fDur = c.duration;
    fBrk = c.breakDuration;
    fCyc = c.cyclesBeforeLongBreak;
  });

  function commitFocusConfig() {
    updateConfig({
      duration: Number(fDur),
      breakDuration: Number(fBrk),
      cyclesBeforeLongBreak: Number(fCyc),
    });
  }

  function handleClose() {
    open = false;
    onClose?.();
  }
</script>

<ModalDialog {open} title={$t('executionPage.optionsTitle')} size="sm" onClose={handleClose}>
  <section class="section">
    <div class="section-title" style="color: var(--xp, var(--accent));">
      <TimerIcon size={12} /> {$t('executionPage.optPomodoro')}
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('widgets.workMinutes')}</span></div>
      <input
        type="number"
        min="1"
        max="180"
        class="setting-input mono"
        bind:value={$workMins}
        disabled={$pomRunning}
        aria-label={$t('widgets.workMinutes')}
      />
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('widgets.breakMinutes')}</span></div>
      <input
        type="number"
        min="1"
        max="120"
        class="setting-input mono"
        bind:value={$breakMins}
        disabled={$pomRunning}
        aria-label={$t('widgets.breakMinutes')}
      />
    </div>
    <p class="hint">{$t('executionPage.optPomodoroHint')}</p>
  </section>

  <section class="section">
    <div class="section-title" style="color: var(--xp, var(--accent));">
      <Crosshair size={12} /> {$t('executionPage.optFocus')}
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('executionPage.focusCfgWork')}</span></div>
      <input
        type="number"
        min="1"
        max="180"
        class="setting-input mono"
        bind:value={fDur}
        onchange={commitFocusConfig}
        aria-label={$t('executionPage.focusCfgWork')}
      />
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('executionPage.focusCfgBreak')}</span></div>
      <input
        type="number"
        min="1"
        max="120"
        class="setting-input mono"
        bind:value={fBrk}
        onchange={commitFocusConfig}
        aria-label={$t('executionPage.focusCfgBreak')}
      />
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('executionPage.focusCfgCycles')}</span></div>
      <input
        type="number"
        min="1"
        max="20"
        class="setting-input mono"
        bind:value={fCyc}
        onchange={commitFocusConfig}
        aria-label={$t('executionPage.focusCfgCycles')}
      />
    </div>
    <p class="hint">{$t('executionPage.focusCfgHint')}</p>
  </section>

  <section class="section">
    <div class="section-title" style="color: var(--xp, var(--accent));">
      <PanelsTopLeft size={12} /> {$t('executionPage.optView')}
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('executionPage.optShowQueue')}</span></div>
      <button
        class="toggle"
        role="switch"
        aria-checked={showQueue}
        aria-label={$t('executionPage.optShowQueue')}
        onclick={() => (showQueue = !showQueue)}
      >
        <span class:active={showQueue}>{$t('executionPage.optOn')}</span>
        <span class="sep">/</span>
        <span class:active={!showQueue}>{$t('executionPage.optOff')}</span>
      </button>
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('executionPage.optShowCalendar')}</span></div>
      <button
        class="toggle"
        role="switch"
        aria-checked={showCalendar}
        aria-label={$t('executionPage.optShowCalendar')}
        onclick={() => (showCalendar = !showCalendar)}
      >
        <span class:active={showCalendar}>{$t('executionPage.optOn')}</span>
        <span class="sep">/</span>
        <span class:active={!showCalendar}>{$t('executionPage.optOff')}</span>
      </button>
    </div>
    <div class="row">
      <div class="row-label"><span>{$t('executionPage.optShowNotes')}</span></div>
      <button
        class="toggle"
        role="switch"
        aria-checked={showNotes}
        aria-label={$t('executionPage.optShowNotes')}
        onclick={() => (showNotes = !showNotes)}
      >
        <span class:active={showNotes}>{$t('executionPage.optOn')}</span>
        <span class="sep">/</span>
        <span class:active={!showNotes}>{$t('executionPage.optOff')}</span>
      </button>
    </div>
  </section>
</ModalDialog>

<style>
  .section {
    padding: 14px 0;
  }
  .section + .section {
    border-top: 1px solid var(--border-light);
  }
  .section-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s3);
    padding: 6px 0;
  }
  .row-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 3px 8px;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .toggle .active {
    color: var(--text-primary);
  }
  .setting-input {
    width: 72px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 6px 10px;
    font-size: 11px;
    color: var(--text-primary);
    text-align: right;
  }
  .setting-input:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: 2px;
  }
  .setting-input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
    margin: 8px 0 0;
  }
</style>
