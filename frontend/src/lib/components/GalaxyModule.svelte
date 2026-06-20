<script lang="ts">
  import { globalProgress, globalLevel } from '$lib/stores/gamification';

  export let size = 200;

  // Fibonacci / golden-angle spiral — same arrangement as sunflower seeds,
  // produces a natural galaxy-disc distribution without any randomness.
  const N = 64;
  const GOLDEN = 137.508 * (Math.PI / 180);
  const ALL_STARS = Array.from({ length: N }, (_, i) => {
    const t  = i / N;
    const r  = Math.sqrt(t) * 42;
    const θ  = i * GOLDEN;
    const x  = 50 + r * Math.cos(θ);
    const y  = 60 + r * Math.sin(θ) * 0.52; // squish into disc
    // Core stars bigger; outer ones tiny
    const sr = i === 0 ? 2.4 : i < 4 ? 1.4 : 0.35 + ((i * 7) % 9) / 9 * 0.55;
    const op = i < 5 ? 1 : 0.5 + ((i * 3) % 7) / 7 * 0.5;
    return { x, y, r: sr, op };
  });

  const STAGE_LABELS = [
    'nebulosa oscura', 'proto-estrella', 'estrella joven', 'sistema solar',
    'cúmulo estelar', 'galaxia espiral', 'universo conocido',
  ];

  $: visibleCount = Math.max(3, Math.floor(($globalProgress / 100) * N));
  $: stars        = ALL_STARS.slice(0, visibleCount);
  $: stageIdx     = Math.min(6, Math.floor(($globalLevel - 1) / (100 / 7)));
  $: stageLabel   = STAGE_LABELS[stageIdx] ?? STAGE_LABELS[6];
  $: coreSize     = 2 + stageIdx * 0.6;
</script>

<div class="galaxy-wrap" style="width:{size}px; height:{size}px;">
  <svg viewBox="0 0 100 120" fill="none" xmlns="http://www.w3.org/2000/svg" class="galaxy-svg">
    <!-- Ambient glow behind core -->
    <radialGradient id="core-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"   stop-color="var(--plant-glow)" stop-opacity="0.35" />
      <stop offset="100%" stop-color="var(--plant-glow)" stop-opacity="0" />
    </radialGradient>
    <ellipse cx="50" cy="60" rx="{12 + stageIdx * 3}" ry="{7 + stageIdx * 1.8}" fill="url(#core-glow)" />

    <!-- Stars -->
    {#each stars as s, i}
      <circle
        cx={s.x} cy={s.y} r={s.r}
        fill={i % 3 === 0 ? 'var(--plant)' : i % 3 === 1 ? 'var(--plant-secondary)' : 'var(--plant-tertiary)'}
        opacity={s.op}
        style="transition: opacity 600ms ease {i * 8}ms"
      />
    {/each}

    <!-- Core star — always visible, pulses -->
    <circle cx="50" cy="60" r={coreSize} fill="var(--plant-secondary)" class="core-pulse" />
  </svg>

  <div class="stage-tag mono">{stageLabel} · niv {$globalLevel}</div>
</div>

<style>
  .galaxy-wrap {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .galaxy-svg {
    width: 100%;
    height: 100%;
  }

  .core-pulse {
    animation: pulse 3s ease-in-out infinite;
    transform-origin: 50px 60px;
  }

  .stage-tag {
    position: absolute;
    bottom: 4px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 9px;
    color: var(--text-muted);
    letter-spacing: 0.06em;
    white-space: nowrap;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.8; r: inherit; }
    50%       { opacity: 1;   transform: scale(1.3); }
  }
</style>
