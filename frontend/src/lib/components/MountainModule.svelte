<script lang="ts">
  import { globalProgress, globalLevel } from '$lib/stores/gamification';

  export let size = 200;

  // Climber moves from base (12, 102) to summit (50, 18) along the left face OVER THE ENTIRE 1-100 levels!
  $: t  = Math.min(1, $globalProgress / 100);
  $: cx = 12 + 38 * t;
  $: cy = 102 - 84 * t;

  // Snow cap appears above 60% global progress (Level 60+)
  $: showSnow = $globalProgress >= 60;
  // Flag appears at Level 100
  $: showFlag = $globalLevel >= 100;

  const ALTITUDE = [
    'base camp', '300m', '600m', 'zona de muerte', '1200m', 'cumbre cercana', '¡cima!'
  ];
  
  $: stageIdx = Math.min(6, Math.floor(($globalLevel - 1) / (100 / 7)));
  $: altLabel = ALTITUDE[stageIdx] ?? ALTITUDE[6];
</script>

<div class="mountain-wrap" style="width:{size}px; height:{size}px;">
  <svg viewBox="0 0 100 120" fill="none" xmlns="http://www.w3.org/2000/svg" class="mountain-svg">
    <!-- Ground -->
    <line x1="5" y1="104" x2="95" y2="104" stroke="var(--plant)" stroke-width="0.6" opacity="0.4"/>

    <!-- Secondary peak (right) -->
    <path d="M 60,104 L 80,55 L 95,104"
      stroke="var(--plant)" stroke-width="1" fill="none" stroke-linejoin="round" opacity="0.35"/>

    <!-- Main mountain -->
    <path d="M 5,104 L 50,18 L 90,104"
      stroke="var(--plant)" stroke-width="1.4" fill="none" stroke-linejoin="round"/>

    <!-- Snow cap -->
    {#if showSnow}
      <path d="M 50,18 L 39,42 L 61,42 Z"
        stroke="var(--plant)" stroke-width="0.8" fill="none" opacity="0.6"
        style="transition: opacity 500ms ease;"/>
    {/if}

    <!-- Progress tick marks along left face -->
    {#each [0.2, 0.4, 0.6, 0.8] as tick}
      {@const tx = 12 + 38 * tick}
      {@const ty = 102 - 84 * tick}
      {#if t >= tick}
        <line
          x1={tx - 3} y1={ty}
          x2={tx}     y2={ty}
          stroke="var(--plant)" stroke-width="0.7" opacity="0.5"
        />
      {/if}
    {/each}

    <!-- Climber (small filled circle + tiny cross for body) -->
    <circle cx={cx} cy={cy} r="2.2" fill="var(--plant)" class="climber" />
    <line x1={cx} y1={cy + 2.5} x2={cx} y2={cy + 5} stroke="var(--plant)" stroke-width="0.8"/>
    <line x1={cx - 2} y1={cy + 3.5} x2={cx + 2} y2={cy + 3.5} stroke="var(--plant)" stroke-width="0.7"/>

    <!-- Summit flag -->
    {#if showFlag}
      <line x1="50" y1="18" x2="50" y2="10" stroke="var(--plant)" stroke-width="0.9"/>
      <polygon points="50,10 56,13 50,16" fill="var(--plant)" opacity="0.8"/>
    {/if}
  </svg>

  <div class="alt-tag mono">{altLabel} · niv {$globalLevel}</div>
</div>

<style>
  .mountain-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .mountain-svg {
    width: 100%;
    height: 100%;
    animation: breathe 5s ease-in-out infinite;
    transform-origin: center bottom;
  }

  .climber {
    transition: cx 800ms ease, cy 800ms ease;
  }

  .alt-tag {
    position: absolute;
    bottom: 4px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    white-space: nowrap;
  }

  @keyframes breathe {
    0%, 100% { transform: scale(1); }
    50%       { transform: scale(1.008) translateY(-1px); }
  }
</style>
