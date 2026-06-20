<script lang="ts">
  import { globalLevel } from '$lib/stores/gamification';

  export let size = 200;

  // Buildings per stage: [x, width, height, windows_cols, windows_rows]
  // x=left edge, all relative to viewBox 0 0 100 120, ground at y=100
  const BUILDINGS_BY_STAGE: [number, number, number, number, number][][] = [
    // 0: semilla — 1 tiny shed
    [[42, 16, 14, 1, 1]],
    // 1: brote — 3 small buildings
    [[18, 14, 18, 1, 2], [40, 18, 22, 2, 2], [68, 14, 16, 1, 2]],
    // 2: plantón — 5 buildings
    [[8, 12, 20, 1, 2], [24, 16, 28, 2, 3], [44, 12, 24, 1, 2], [60, 18, 32, 2, 3], [82, 10, 18, 1, 2]],
    // 3: joven — 7 buildings
    [[5, 11, 22, 1, 2], [18, 14, 30, 1, 3], [33, 16, 38, 2, 4], [50, 12, 26, 1, 3], [63, 18, 45, 2, 4], [82, 12, 28, 1, 3], [92, 8, 18, 1, 2]],
    // 4: madura — 9 buildings, central tower
    [[3, 10, 24, 1, 2], [14, 12, 32, 1, 3], [27, 14, 40, 2, 4], [40, 10, 28, 1, 3], [50, 16, 60, 2, 6], [67, 12, 36, 1, 4], [79, 14, 42, 2, 4], [89, 10, 26, 1, 3], [95, 5, 14, 1, 2]],
    // 5: floreciendo — 11 buildings
    [[2, 9, 26, 1, 3], [12, 11, 34, 1, 4], [23, 13, 44, 2, 5], [35, 10, 30, 1, 3], [45, 6, 52, 1, 5], [51, 18, 68, 3, 7], [70, 12, 48, 2, 5], [82, 13, 38, 2, 4], [90, 10, 28, 1, 3], [96, 4, 18, 1, 2]],
    // 6: árbol — full skyline
    [[1, 8, 28, 1, 3], [10, 10, 36, 1, 4], [20, 12, 46, 2, 5], [31, 9, 32, 1, 4], [40, 6, 55, 1, 6], [46, 20, 78, 3, 8], [67, 11, 50, 2, 5], [78, 13, 40, 2, 4], [87, 10, 30, 1, 3], [94, 5, 20, 1, 2]],
  ];

  $: stageIdx = Math.min(6, Math.floor(($globalLevel - 1) / (100 / 7)));
  $: buildings = BUILDINGS_BY_STAGE[stageIdx] ?? BUILDINGS_BY_STAGE[0];

  function windowsFor(x: number, bw: number, bh: number, cols: number, rows: number) {
    const wins: { x: number; y: number }[] = [];
    const padX = 3, padY = 4;
    const cellW = (bw - padX * 2) / cols;
    const cellH = (bh - padY * 2) / rows;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        wins.push({
          x: x + padX + c * cellW + cellW * 0.2,
          y: 100 - bh + padY + r * cellH + cellH * 0.2,
        });
      }
    }
    return wins;
  }
</script>

<div class="city-wrap" style="width:{size}px; height:{size}px;">
  <svg viewBox="0 0 100 120" fill="none" xmlns="http://www.w3.org/2000/svg" class="city-svg">
    <!-- Moon / night atmosphere -->
    <circle cx="82" cy="22" r="6" stroke="var(--plant-secondary)" stroke-width="0.6" fill="none" opacity="0.4"/>
    <circle cx="80" cy="21" r="5" fill="var(--bg)" />

    <!-- Ground -->
    <line x1="0" y1="100" x2="100" y2="100" stroke="var(--plant)" stroke-width="0.7" opacity="0.4"/>

    <!-- Buildings -->
    {#each buildings as [bx, bw, bh, cols, rows], bi}
      <rect
        x={bx} y={100 - bh} width={bw} height={bh}
        stroke={bi % 2 === 0 ? 'var(--plant)' : 'var(--plant-secondary)'} stroke-width="0.8" fill="var(--bg)"
        style="transition: height 600ms ease {bi * 80}ms, y 600ms ease {bi * 80}ms"
      />
      <!-- Windows -->
      {#each windowsFor(bx, bw, bh, cols, rows) as w}
        <rect
          x={w.x} y={w.y}
          width={(bw - 6) / cols * 0.55}
          height={(bh - 8) / rows * 0.5}
          fill="var(--plant-tertiary)" opacity="0.4"
        />
      {/each}
    {/each}
  </svg>

  <div class="city-tag mono">ciudad nivel {$globalLevel}</div>
</div>

<style>
  .city-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .city-svg {
    width: 100%;
    height: 100%;
  }

  .city-tag {
    position: absolute;
    bottom: 4px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    white-space: nowrap;
  }
</style>
