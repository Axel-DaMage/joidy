<script lang="ts">
  import { Play, Pause, Flag, RotateCcw } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import {
    formatStopwatch,
    lapStopwatch,
    pauseStopwatch,
    resetStopwatch,
    startStopwatch,
    stopwatch,
    stopwatchElapsed,
    type Lap,
  } from '$lib/stores/timers';

  $: laps = $stopwatch.laps;
  $: fastestN = bestWorst(laps).fastest;
  $: slowestN = bestWorst(laps).slowest;

  function bestWorst(ls: Lap[]): { fastest: number | null; slowest: number | null } {
    if (ls.length < 2) return { fastest: null, slowest: null };
    let fastest = ls[0];
    let slowest = ls[0];
    for (const l of ls) {
      if (l.lapMs < fastest.lapMs) fastest = l;
      if (l.lapMs > slowest.lapMs) slowest = l;
    }
    return { fastest: fastest.n, slowest: slowest.n };
  }
</script>

<div class="stopwatch-panel">
  <div class="display card">
    <span class="sw-time mono" class:running={$stopwatch.running}>
      {formatStopwatch($stopwatchElapsed)}
    </span>
    <div class="controls">
      {#if !$stopwatch.running}
        <button type="button" class="btn btn-primary" onclick={startStopwatch}>
          <Play size={14} />
          {$t('timers.stopwatch.start')}
        </button>
      {:else}
        <button type="button" class="btn" onclick={pauseStopwatch}>
          <Pause size={14} />
          {$t('timers.stopwatch.pause')}
        </button>
        <button type="button" class="btn" onclick={lapStopwatch}>
          <Flag size={14} />
          {$t('timers.stopwatch.lap')}
        </button>
      {/if}
      <button
        type="button"
        class="btn btn-ghost"
        onclick={resetStopwatch}
        disabled={!$stopwatch.running && $stopwatch.baseMs === 0 && laps.length === 0}
      >
        <RotateCcw size={14} />
        {$t('timers.stopwatch.reset')}
      </button>
    </div>
  </div>

  {#if laps.length > 0}
    <div class="laps card">
      <table>
        <thead>
          <tr>
            <th>{$t('timers.stopwatch.lapCol')}</th>
            <th>{$t('timers.stopwatch.lapTime')}</th>
            <th>{$t('timers.stopwatch.total')}</th>
          </tr>
        </thead>
        <tbody>
          {#each [...laps].reverse() as lap (lap.n)}
            <tr class:fastest={lap.n === fastestN} class:slowest={lap.n === slowestN}>
              <td class="mono">
                {lap.n}
                {#if lap.n === fastestN}<span class="tag fast"
                    >{$t('timers.stopwatch.fastest')}</span
                  >{/if}
                {#if lap.n === slowestN}<span class="tag slow"
                    >{$t('timers.stopwatch.slowest')}</span
                  >{/if}
              </td>
              <td class="mono">{formatStopwatch(lap.lapMs)}</td>
              <td class="mono">{formatStopwatch(lap.totalMs)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .stopwatch-panel {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .display {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
    padding: 32px 20px;
  }
  .sw-time {
    font-size: clamp(40px, 9vw, 64px);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
  }
  .sw-time.running {
    color: var(--accent);
  }
  .controls {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .laps {
    padding: 8px 0;
    overflow: hidden;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  th {
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 6px 14px;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 7px 14px;
    border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
  }
  tr:last-child td {
    border-bottom: none;
  }
  tr.fastest td {
    color: var(--success, #22c55e);
  }
  tr.slowest td {
    color: var(--danger, #ef4444);
  }
  .tag {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    margin-left: 6px;
    padding: 1px 5px;
    border-radius: 4px;
  }
  .tag.fast {
    background: color-mix(in srgb, var(--success, #22c55e) 15%, transparent);
  }
  .tag.slow {
    background: color-mix(in srgb, var(--danger, #ef4444) 15%, transparent);
  }
</style>
