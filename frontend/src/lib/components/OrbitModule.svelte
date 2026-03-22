<script lang="ts">
  import { plantStage } from '$lib/stores/gamification';

  export let size = 200;

  // Each planet: [name, orbit_rx, orbit_ry, planet_r, period_s, start_angle_deg]
  const PLANETS = [
    ['Mercurio', 16, 6,  2,   4, 0  ],
    ['Venus',    24, 9,  2.5, 7, 60 ],
    ['Tierra',   32, 12, 3,   11, 130],
    ['Marte',    40, 15, 2.5, 18, 200],
    ['Júpiter',  48, 18, 4,   28, 290],
    ['Saturno',  54, 20, 3.5, 40, 45 ],
  ] as const;

  $: visiblePlanets = PLANETS.slice(0, Math.max(1, $plantStage));
</script>

<div class="orbit-wrap" style="width:{size}px; height:{size}px;">
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" class="orbit-svg">
    <!-- Sun -->
    <circle cx="50" cy="50" r="5" fill="var(--plant)" class="sun-pulse"/>
    <circle cx="50" cy="50" r="7" stroke="var(--plant)" stroke-width="0.5" opacity="0.3"/>

    <!-- Orbit paths + planets -->
    {#each visiblePlanets as [name, rx, ry, pr, period], i}
      <!-- Orbit ellipse -->
      <ellipse cx="50" cy="50" rx={rx} ry={ry}
        stroke="var(--plant)" stroke-width="0.4" stroke-dasharray="2 2" opacity="0.3"/>

      <!-- Planet group rotates around sun -->
      <g
        class="planet-orbit"
        style="transform-origin: 50px 50px; animation-duration: {period}s; animation-delay: -{period * 0.15 * i}s"
      >
        <!-- Planet offset along orbit's X axis -->
        <g style="transform: translateX({rx}px)">
          <circle cx="0" cy="0" r={pr} fill="var(--plant)" opacity="0.85"/>
          <!-- Saturn ring -->
          {#if i === 5}
            <ellipse cx="0" cy="0" rx={pr + 2.5} ry="1.2"
              stroke="var(--plant)" stroke-width="0.5" fill="none" opacity="0.6"/>
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

  .orbit-svg {
    width: 100%;
    height: 100%;
  }

  .sun-pulse {
    animation: sun-glow 2.5s ease-in-out infinite;
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
    0%, 100% { opacity: 0.85; r: 5px; }
    50%       { opacity: 1;   r: 5.8px; }
  }
</style>
