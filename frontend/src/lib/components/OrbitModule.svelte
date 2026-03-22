<script lang="ts">
  import { plantStage } from '$lib/stores/gamification';

  export let size = 200;

  // Orbits scaled so the outermost (Saturn, rx=42) fits in the 100×100 viewBox
  // center=(50,50), max radius ~44 to leave a 3px margin on each side
  const PLANETS = [
    ['Mercurio', 12, 4.5,  2,    4, 0  ],
    ['Venus',    18, 6.5,  2.5,  7, 60 ],
    ['Tierra',   25, 9,    3,    11, 130],
    ['Marte',    31, 11,   2.5,  18, 200],
    ['Júpiter',  37, 13.5, 4,    28, 290],
    ['Saturno',  42, 15.5, 3.5,  40, 45 ],
  ] as const;

  $: visiblePlanets = PLANETS.slice(0, Math.max(1, $plantStage));
</script>

<div class="orbit-wrap" style="width:{size}px; height:{size}px;">
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" class="orbit-svg">
    <!-- Sun glow -->
    <circle cx="50" cy="50" r="9"  fill="var(--plant)" opacity="0.08"/>
    <circle cx="50" cy="50" r="5"  fill="var(--plant)" class="sun-pulse"/>

    <!-- Orbit ellipses + planets -->
    {#each visiblePlanets as [name, rx, ry, pr, period], i}
      <ellipse cx="50" cy="50" rx={rx} ry={ry}
        stroke="var(--plant)" stroke-width="0.35" stroke-dasharray="2 1.5" opacity="0.25"/>

      <g class="planet-orbit"
        style="transform-origin:50px 50px; animation-duration:{period}s; animation-delay:-{(period * 0.17 * i).toFixed(1)}s">
        <g style="transform:translateX({rx}px)">
          <circle cx="0" cy="0" r={pr} fill="var(--plant)" opacity="0.9"/>
          {#if i === 5}
            <!-- Saturn ring -->
            <ellipse cx="0" cy="0" rx={pr + 2.5} ry="1.3"
              stroke="var(--plant)" stroke-width="0.5" fill="none" opacity="0.55"/>
          {/if}
        </g>
      </g>
    {/each}
  </svg>

  <div class="orbit-tag mono">{visiblePlanets.length} planeta{visiblePlanets.length !== 1 ? 's' : ''}</div>
</div>

<style>
  .orbit-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .orbit-svg { width: 100%; height: 100%; }

  .sun-pulse {
    animation: sun-glow 2.5s ease-in-out infinite;
    transform-origin: 50px 50px;
  }

  .planet-orbit {
    animation: orbit linear infinite;
  }

  .orbit-tag {
    position: absolute;
    bottom: 2px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    white-space: nowrap;
  }

  @keyframes orbit {
    from { transform: rotate(0deg);   }
    to   { transform: rotate(360deg); }
  }

  @keyframes sun-glow {
    0%, 100% { opacity: 0.85; }
    50%       { opacity: 1;   }
  }
</style>
