<script lang="ts">
  import { fly } from 'svelte/transition';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';

  let {
    title,
    icon,
    value,
    subtitle,
    color = 'var(--xp)'
  }: {
    title: string;
    icon: string;
    value: string;
    subtitle?: string;
    color?: string;
  } = $props();

  // Respect prefers-reduced-motion: when set, skip the entrance animation.
  let reducedMotion = $state(false);

  function updateMotion() {
    if (typeof window === 'undefined') return;
    reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  $effect(() => {
    if (typeof window === 'undefined') return;
    updateMotion();
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handler = () => updateMotion();
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  });
</script>

<div
  class="achievement-card"
  style="--ach-color: {color};"
  in:fly={reducedMotion ? { duration: 0 } : { y: 12, duration: 260, opacity: 0 }}
>
  <div class="card-glow"></div>

  <div class="card-inner">
    <div class="card-icon">
      <DynamicIcon name={icon} size={40} />
    </div>

    <div class="card-content">
      <span class="card-value mono">{value}</span>
      <span class="card-title">{title}</span>
      {#if subtitle}
        <span class="card-subtitle">{subtitle}</span>
      {/if}
    </div>
  </div>

  <div class="card-brand">
    <span class="brand-name mono">JOIDY</span>
  </div>
</div>

<style>
  .achievement-card {
    position: relative;
    width: 320px;
    border-radius: var(--r-xl);
    overflow: hidden;
    background: linear-gradient(
      135deg,
      color-mix(in srgb, var(--ach-color) 28%, var(--elevated)) 0%,
      var(--elevated) 60%,
      color-mix(in srgb, var(--ach-color) 12%, var(--bg)) 100%
    );
    border: 1px solid color-mix(in srgb, var(--ach-color) 40%, var(--border));
    box-shadow:
      0 18px 40px rgba(0, 0, 0, 0.45),
      0 0 0 1px color-mix(in srgb, var(--ach-color) 10%, transparent);
    isolation: isolate;
  }

  .card-glow {
    position: absolute;
    top: -60px;
    right: -60px;
    width: 180px;
    height: 180px;
    border-radius: 50%;
    background: radial-gradient(
      circle,
      color-mix(in srgb, var(--ach-color) 55%, transparent) 0%,
      transparent 70%
    );
    filter: blur(8px);
    pointer-events: none;
    z-index: 0;
  }

  .card-inner {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: var(--s4);
    padding: var(--s5);
  }

  .card-icon {
    flex-shrink: 0;
    width: 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--r-lg);
    background: color-mix(in srgb, var(--ach-color) 22%, transparent);
    color: var(--ach-color);
    border: 1px solid color-mix(in srgb, var(--ach-color) 35%, transparent);
  }

  .card-content {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .card-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--ach-color);
    line-height: 1.1;
    letter-spacing: -0.01em;
  }

  .card-title {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    line-height: 1.2;
  }

  .card-subtitle {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 2px;
  }

  .card-brand {
    position: relative;
    z-index: 1;
    display: flex;
    justify-content: flex-end;
    padding: var(--s2) var(--s4) var(--s3);
  }

  .brand-name {
    font-size: 9px;
    letter-spacing: 0.18em;
    color: var(--text-muted);
    opacity: 0.7;
  }
</style>
