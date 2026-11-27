<script lang="ts">
  import { Copy, Flag, Pause, Play, RotateCcw } from 'lucide-svelte';
  import { t } from 'svelte-i18n';
  import { logger } from '$lib/utils/logger';
  import { showNotification } from '$lib/stores/notifications';
  import {
    formatSignedDelta,
    formatStopwatch,
    lapStopwatch,
    pauseStopwatch,
    resetStopwatch,
    startStopwatch,
    stopwatch,
    stopwatchElapsed,
    type Lap,
  } from '$lib/stores/timers';

  const laps = $derived($stopwatch.laps);
  const bestWorst = $derived.by(() => {
    if (laps.length < 2) return { fastest: null as number | null, slowest: null as number | null };
    let fastest = laps[0];
    let slowest = laps[0];
    for (const l of laps) {
      if (l.lapMs < fastest.lapMs) fastest = l;
      if (l.lapMs > slowest.lapMs) slowest = l;
    }
    return { fastest: fastest.n, slowest: slowest.n };
  });

  /** Lap n's delta vs the previous lap — positive means slower (#1663). */
  function delta(n: number): number | null {
    if (n < 2) return null;
    const cur = laps[n - 1];
    const prev = laps[n - 2];
    if (!cur || !prev) return null;
    return cur.lapMs - prev.lapMs;
  }

  /** Live segment in progress — time since the last recorded lap. */
  const currentLapMs = $derived.by(() => {
    const last = laps.length ? laps[laps.length - 1].totalMs : 0;
    return Math.max(0, $stopwatchElapsed - last);
  });

  const idle = $derived(!$stopwatch.running && $stopwatch.baseMs === 0 && laps.length === 0);

  async function copyLaps() {
    const text = laps
      .map((l: Lap) => `${l.n}\t${formatStopwatch(l.lapMs)}\t${formatStopwatch(l.totalMs)}`)
      .join('\n');
    try {
      await navigator.clipboard.writeText(text);
      showNotification($t('timers.stopwatch.copied'), 'info');
    } catch (e) {
      logger.warn('[timers] clipboard copy failed:', e);
    }
  }
</script>

<div class="stopwatch-panel">
  <div class="display">
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
      <button type="button" class="btn btn-ghost" onclick={resetStopwatch} disabled={idle}>
        <RotateCcw size={14} />
        {$t('timers.stopwatch.reset')}
      </button>
      {#if laps.length > 0}
        <button type="button" class="btn btn-ghost" onclick={copyLaps}>
          <Copy size={14} />
          {$t('timers.stopwatch.copy')}
        </button>
      {/if}
    </div>
  </div>

  {#if laps.length > 0}
    <div class="laps">
      <table>
        <thead>
          <tr>
            <th>{$t('timers.stopwatch.lapCol')}</th>
            <th>{$t('timers.stopwatch.delta')}</th>
            <th>{$t('timers.stopwatch.lapTime')}</th>
            <th>{$t('timers.stopwatch.total')}</th>
          </tr>
        </thead>
        <tbody>
          {#if $stopwatch.running}
            <tr class="current">
              <td class="mono">
                {laps.length + 1}
                <span class="tag live">{$t('timers.stopwatch.currentLap')}</span>
              </td>
              <td class="mono">—</td>
              <td class="mono">{formatStopwatch(currentLapMs)}</td>
              <td class="mono">{formatStopwatch($stopwatchElapsed)}</td>
            </tr>
          {/if}
          {#each [...laps].reverse() as lap (lap.n)}
            {@const d = delta(lap.n)}
            <tr class:fastest={lap.n === bestWorst.fastest} class:slowest={lap.n === bestWorst.slowest}>
              <td class="mono">
                {lap.n}
                {#if lap.n === bestWorst.fastest}
                  <span class="tag fast">{$t('timers.stopwatch.fastest')}</span>
                {/if}
                {#if lap.n === bestWorst.slowest}
                  <span class="tag slow">{$t('timers.stopwatch.slowest')}</span>
                {/if}
              </td>
              <td class="mono delta" class:pos={d !== null && d > 0} class:neg={d !== null && d < 0}>
                {d === null ? '—' : formatSignedDelta(d)}
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
    gap: var(--s3);
  }
  .display {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s4);
    padding: var(--s5) var(--s4) var(--s3);
  }
  .sw-time {
    font-size: clamp(36px, 7vw, 56px);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: var(--text-primary);
    line-height: 1.1;
  }
  .sw-time.running {
    color: var(--xp);
  }
  .controls {
    display: flex;
    gap: var(--s2);
    flex-wrap: wrap;
    justify-content: center;
  }
  .laps {
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
    padding: var(--s1_5) var(--s3);
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: var(--s1_5) var(--s3);
    border-bottom: 1px solid color-mix(in srgb, var(--border) 50%, transparent);
  }
  tr:last-child td {
    border-bottom: none;
  }
  tr.current td {
    color: var(--xp-2);
    font-weight: 600;
  }
  tr.fastest td {
    color: var(--success);
  }
  tr.slowest td {
    color: var(--error);
  }
  .delta.pos {
    color: var(--error);
  }
  .delta.neg {
    color: var(--success);
  }
  .tag {
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    margin-left: var(--s1_5);
    padding: 1px var(--s1_5);
    border-radius: var(--r);
  }
  .tag.fast {
    background: color-mix(in srgb, var(--success) 15%, transparent);
  }
  .tag.slow {
    background: color-mix(in srgb, var(--error) 15%, transparent);
  }
  .tag.live {
    background: color-mix(in srgb, var(--xp) 15%, transparent);
    color: var(--xp-2);
  }
</style>
