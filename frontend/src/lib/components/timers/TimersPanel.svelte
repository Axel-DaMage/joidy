<script lang="ts">
  import { onMount } from 'svelte';
  import { SvelteMap } from 'svelte/reactivity';
  import {
    FileText,
    Pause,
    Play,
    Plus,
    Repeat,
    RotateCcw,
    Sparkles,
    Target,
    Timer,
    X,
  } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { api, type Goal, type Note } from '$lib/api';
  import { logger } from '$lib/utils/logger';
  import NoteLinkPicker from '$lib/components/NoteLinkPicker.svelte';
  import {
    addMinuteToTimer,
    addTimer,
    formatHMS,
    pauseTimer,
    removeTimer,
    resetTimer,
    restartTimer,
    resumeTimer,
    timers,
    timersRemaining,
    type TimerItem,
  } from '$lib/stores/timers';

  interface Preset {
    minutes: number;
    key: string;
    awardXp?: boolean;
  }
  const PRESETS: Preset[] = [
    { minutes: 25, key: 'timers.timer.pomodoro', awardXp: true },
    { minutes: 5, key: 'timers.timer.shortBreak' },
    { minutes: 15, key: 'timers.timer.longBreak' },
    { minutes: 1, key: 'timers.timer.presetMins' },
    { minutes: 10, key: 'timers.timer.presetMins' },
    { minutes: 60, key: 'timers.timer.presetMins' },
  ];

  /** Ring swatches — the first entry is "default" (falls back to --xp). */
  const COLOR_SWATCHES = [
    '#f59e0b',
    '#10b981',
    '#06b6d4',
    '#8b5cf6',
    '#ec4899',
    '#ef4444',
  ];

  let hours = $state(0);
  let minutes = $state(5);
  let seconds = $state(0);
  let label = $state('');
  let color = $state<string | null>(null);
  let goalId = $state<number | null>(null);
  let noteId = $state<number | null>(null);
  let awardXp = $state(false);
  let repeat = $state(false);

  let goals = $state<Goal[]>([]);
  let notes = $state<Note[]>([]);

  onMount(() => {
    // Linked-entity pickers are best-effort: offline/API errors just leave
    // the selects empty (#1663).
    api.goals
      .list(0, 100, { state: 'ACTIVE' })
      .then((g) => (goals = g))
      .catch((e: unknown) => logger.warn('[timers] goal list unavailable:', e));
    api.notes
      .list(undefined, 60)
      .then((n) => (notes = n))
      .catch((e: unknown) => logger.warn('[timers] note list unavailable:', e));
  });

  const durationMs = $derived(
    ((hours || 0) * 3600 + (minutes || 0) * 60 + (seconds || 0)) * 1000
  );

  function timerOpts() {
    return {
      color: color ?? undefined,
      goalId,
      noteId,
      awardXp,
      repeat,
    };
  }

  function startCustom() {
    if (durationMs < 1000) return;
    addTimer(label.trim(), durationMs, timerOpts());
    label = '';
  }

  function startPreset(p: Preset) {
    const presetLabel = label.trim() || $t(p.key, { values: { minutes: p.minutes } });
    addTimer(presetLabel, p.minutes * 60_000, {
      ...timerOpts(),
      awardXp: p.awardXp ?? awardXp,
    });
    label = '';
  }

  function progress(tm: TimerItem, remaining: number): number {
    if (tm.totalMs <= 0) return 0;
    return Math.max(0, Math.min(1, remaining / tm.totalMs));
  }

  const goalTitle = $derived.by(() => {
    const map = new SvelteMap<number, string>();
    for (const g of goals) map.set(g.id, g.title);
    return map;
  });
  const noteTitle = $derived.by(() => {
    const map = new SvelteMap<number, string>();
    for (const n of notes) map.set(n.id, n.title);
    return map;
  });

  // SVG ring geometry
  const R = 34;
  const CIRC = 2 * Math.PI * R;
</script>

<div class="timers-panel">
  <div class="new-timer">
    <div class="presets" role="group" aria-label={$t('timers.timer.presets')}>
      {#each PRESETS as p (p.minutes + p.key)}
        <button type="button" class="btn-ghost preset" onclick={() => startPreset(p)}>
          {#if p.awardXp}<Sparkles size={11} />{/if}
          {$t(p.key, { values: { minutes: p.minutes } })}
        </button>
      {/each}
    </div>

    <div class="custom-row">
      <div class="hms">
        <label class="hms-field">
          <input
            class="input mono"
            type="number"
            min="0"
            max="23"
            bind:value={hours}
            aria-label={$t('timers.timer.hours')}
          />
          <span class="muted">{$t('timers.timer.hoursShort')}</span>
        </label>
        <label class="hms-field">
          <input
            class="input mono"
            type="number"
            min="0"
            max="59"
            bind:value={minutes}
            aria-label={$t('timers.timer.minutes')}
          />
          <span class="muted">{$t('timers.timer.minutesShort')}</span>
        </label>
        <label class="hms-field">
          <input
            class="input mono"
            type="number"
            min="0"
            max="59"
            bind:value={seconds}
            aria-label={$t('timers.timer.seconds')}
          />
          <span class="muted">{$t('timers.timer.secondsShort')}</span>
        </label>
      </div>
      <input
        class="input grow"
        type="text"
        maxlength="80"
        placeholder={$t('timers.timer.labelPlaceholder')}
        bind:value={label}
        onkeydown={(e) => e.key === 'Enter' && startCustom()}
      />
      <button
        type="button"
        class="btn btn-primary"
        disabled={durationMs < 1000}
        onclick={startCustom}
      >
        <Play size={14} />
        {$t('timers.timer.start')}
      </button>
    </div>

    <div class="options-row">
      <div class="opt swatches" role="group" aria-label={$t('timers.timer.color')}>
        <button
          type="button"
          class="swatch default"
          class:on={color === null}
          title={$t('timers.timer.colorDefault')}
          aria-label={$t('timers.timer.colorDefault')}
          aria-pressed={color === null}
          onclick={() => (color = null)}></button>
        {#each COLOR_SWATCHES as c (c)}
          <button
            type="button"
            class="swatch"
            class:on={color === c}
            style:background={c}
            title={c}
            aria-label={c}
            aria-pressed={color === c}
            onclick={() => (color = c)}></button>
        {/each}
      </div>

      {#if goals.length > 0}
        <label class="opt select-wrap" title={$t('timers.timer.linkGoal')}>
          <Target size={13} />
          <select class="input" bind:value={goalId} aria-label={$t('timers.timer.linkGoal')}>
            <option value={null}>{$t('timers.timer.noGoal')}</option>
            {#each goals as g (g.id)}
              <option value={g.id}>{g.title}</option>
            {/each}
          </select>
        </label>
      {/if}

      {#if notes.length > 0}
        <div class="opt note-wrap">
          <FileText size={13} />
          <NoteLinkPicker
            {notes}
            bind:value={noteId}
            placeholder={$t('timers.timer.notePlaceholder')}
          />
        </div>
      {/if}

      <label class="opt check" title={$t('timers.timer.awardXpHint')}>
        <input type="checkbox" bind:checked={awardXp} />
        <Sparkles size={12} />
        <span>{$t('timers.timer.awardXp')}</span>
      </label>
      <label class="opt check" title={$t('timers.timer.repeatHint')}>
        <input type="checkbox" bind:checked={repeat} />
        <Repeat size={12} />
        <span>{$t('timers.timer.repeat')}</span>
      </label>
    </div>
  </div>

  {#if $timers.length === 0}
    <div class="empty">
      <Timer size={26} strokeWidth={1.5} />
      <p class="muted">{$t('timers.timer.empty')}</p>
    </div>
  {:else}
    <div class="timer-grid">
      {#each $timers as tm (tm.id)}
        {@const remaining = $timersRemaining.get(tm.id) ?? tm.remainingMs}
        <div
          class="timer-card"
          class:done={tm.status === 'done'}
          style:border-color={tm.status === 'done' && tm.color ? tm.color : null}
        >
          <button
            type="button"
            class="close"
            aria-label={$t('common.delete')}
            onclick={() => removeTimer(tm.id)}><X size={13} /></button
          >
          <div class="ring-wrap">
            <svg viewBox="0 0 80 80" class="ring" aria-hidden="true">
              <circle cx="40" cy="40" r={R} class="ring-bg" />
              <circle
                cx="40"
                cy="40"
                r={R}
                class="ring-fg"
                class:finished={tm.status === 'done' && !tm.color}
                style:stroke={tm.color || null}
                stroke-dasharray={CIRC}
                stroke-dashoffset={CIRC * (1 - progress(tm, remaining))}
              />
            </svg>
            <span class="ring-time mono">{formatHMS(remaining)}</span>
          </div>
          {#if tm.label}<span class="timer-label">{tm.label}</span>{/if}
          <div class="timer-tags">
            {#if tm.goalId && goalTitle.get(tm.goalId)}
              <span class="tag" title={$t('timers.timer.linkGoal')}>
                <Target size={10} />
                {goalTitle.get(tm.goalId)}
              </span>
            {/if}
            {#if tm.noteId && noteTitle.get(tm.noteId)}
              <span class="tag" title={$t('timers.timer.linkNote')}>
                <FileText size={10} />
                {noteTitle.get(tm.noteId)}
              </span>
            {/if}
            {#if tm.awardXp}
              <span class="tag xp" title={$t('timers.timer.awardXp')}>
                <Sparkles size={10} />
                XP
              </span>
            {/if}
            {#if tm.repeat}
              <span class="tag" title={$t('timers.timer.repeat')}>
                <Repeat size={10} />
              </span>
            {/if}
          </div>
          <div class="timer-actions">
            {#if tm.status === 'done'}
              <button
                type="button"
                class="btn-icon"
                aria-label={$t('timers.timer.restart')}
                title={$t('timers.timer.restart')}
                onclick={() => restartTimer(tm.id)}><RotateCcw size={14} /></button
              >
            {:else}
              {#if tm.status === 'running'}
                <button
                  type="button"
                  class="btn-icon"
                  aria-label={$t('timers.timer.pause')}
                  title={$t('timers.timer.pause')}
                  onclick={() => pauseTimer(tm.id)}><Pause size={14} /></button
                >
              {:else}
                <button
                  type="button"
                  class="btn-icon"
                  aria-label={$t('timers.timer.resume')}
                  title={$t('timers.timer.resume')}
                  onclick={() => resumeTimer(tm.id)}><Play size={14} /></button
                >
              {/if}
              <button
                type="button"
                class="btn-icon"
                aria-label={$t('timers.timer.plusOne')}
                title={$t('timers.timer.plusOne')}
                onclick={() => addMinuteToTimer(tm.id)}><Plus size={14} /></button
              >
              <button
                type="button"
                class="btn-icon"
                aria-label={$t('timers.timer.reset')}
                title={$t('timers.timer.reset')}
                onclick={() => resetTimer(tm.id)}><RotateCcw size={14} /></button
              >
            {/if}
          </div>
          {#if tm.status === 'done'}
            <span class="done-tag">{$t('timers.timer.done')}</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .timers-panel {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
  }
  .new-timer {
    display: flex;
    flex-direction: column;
    gap: var(--s3);
    padding-bottom: var(--s3);
    border-bottom: 1px solid var(--border);
  }
  .presets {
    display: flex;
    gap: var(--s1_5);
    flex-wrap: wrap;
  }
  .preset {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    padding: var(--s1_5) var(--s3);
    font-size: 12px;
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    color: var(--text-secondary);
  }
  .custom-row {
    display: flex;
    gap: var(--s2);
    align-items: center;
    flex-wrap: wrap;
  }
  .hms {
    display: flex;
    gap: var(--s1_5);
  }
  .hms-field {
    display: flex;
    align-items: center;
    gap: var(--s1);
  }
  .hms-field input {
    width: 52px;
    text-align: center;
  }
  .hms-field span {
    font-size: 11px;
  }
  .grow {
    flex: 1;
    min-width: 120px;
  }
  .options-row {
    display: flex;
    align-items: center;
    gap: var(--s3);
    flex-wrap: wrap;
  }
  .opt {
    display: inline-flex;
    align-items: center;
    gap: var(--s1_5);
    color: var(--text-muted);
    font-size: 12px;
  }
  .swatches {
    gap: var(--s1);
  }
  .swatch {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 1px solid var(--border);
    cursor: pointer;
    padding: 0;
    transition:
      transform var(--t-fast),
      border-color var(--t-fast);
  }
  .swatch:hover {
    transform: scale(1.15);
  }
  .swatch.on {
    border-color: var(--text-primary);
    box-shadow: 0 0 0 1px var(--surface), 0 0 0 3px var(--text-primary);
  }
  .swatch.default {
    background: var(--xp);
  }
  .select-wrap .input {
    width: auto;
    min-width: 130px;
    padding: var(--s1) var(--s2);
    font-size: 12px;
  }
  .note-wrap {
    flex: 1;
    min-width: 150px;
    max-width: 220px;
  }
  .check {
    cursor: pointer;
    user-select: none;
  }
  .check input {
    accent-color: var(--xp);
    margin: 0;
  }
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s3);
    padding: var(--s6) var(--s4);
    color: var(--text-muted);
  }
  .timer-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--s2);
  }
  .timer-card {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s2);
    padding: var(--s3) var(--s2) var(--s2);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
  }
  .timer-card.done {
    border-color: var(--xp-2);
  }
  .close {
    position: absolute;
    top: var(--s1_5);
    right: var(--s1_5);
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: var(--s1);
    border-radius: var(--r);
  }
  .close:hover {
    color: var(--error);
  }
  .ring-wrap {
    position: relative;
    width: 80px;
    height: 80px;
  }
  .ring {
    width: 100%;
    height: 100%;
    transform: rotate(-90deg);
  }
  .ring-bg {
    fill: none;
    stroke: var(--border);
    stroke-width: 5;
  }
  .ring-fg {
    fill: none;
    stroke: var(--xp);
    stroke-width: 5;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.25s linear;
  }
  .ring-fg.finished {
    stroke: var(--success);
  }
  .ring-time {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .timer-label {
    font-size: 12px;
    color: var(--text-primary);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .timer-tags {
    display: flex;
    gap: var(--s1);
    flex-wrap: wrap;
    justify-content: center;
    min-height: 0;
  }
  .tag {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 10px;
    color: var(--text-muted);
    border: 1px solid var(--border);
    border-radius: var(--r-full);
    padding: 1px var(--s1_5);
    max-width: 110px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tag.xp {
    color: var(--xp-2);
    border-color: var(--xp-3);
  }
  .timer-actions {
    display: flex;
    gap: 2px;
  }
  .done-tag {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--success);
  }
  @media (prefers-reduced-motion: reduce) {
    .ring-fg,
    .swatch {
      transition: none;
    }
  }
</style>
