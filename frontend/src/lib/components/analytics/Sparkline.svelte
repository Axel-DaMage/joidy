<script lang="ts">
  import { scaleLinear, line, area, curveMonotoneX } from 'd3';

  // Tiny area sparkline used inside the KPI rail. Fills its container.
  let { values = [], color = 'var(--xp)' }: { values?: number[]; color?: string } = $props();

  let w = $state(0);
  let h = $state(0);
  const PAD = 3;

  let pts = $derived(values.map((v, i) => ({ i, v })));
  let x = $derived(
    scaleLinear()
      .domain([0, Math.max(1, values.length - 1)])
      .range([PAD, Math.max(PAD + 1, w - PAD)])
  );
  let y = $derived(
    scaleLinear()
      .domain([0, Math.max(1, ...values)])
      .range([Math.max(PAD + 1, h - PAD), PAD])
  );
  let linePath = $derived(
    line<{ i: number; v: number }>()
      .x((p) => x(p.i))
      .y((p) => y(p.v))
      .curve(curveMonotoneX)(pts) ?? ''
  );
  let areaPath = $derived(
    area<{ i: number; v: number }>()
      .x((p) => x(p.i))
      .y0(Math.max(PAD + 1, h - PAD))
      .y1((p) => y(p.v))
      .curve(curveMonotoneX)(pts) ?? ''
  );
  const gid = `sg${Math.random().toString(36).slice(2, 8)}`;
</script>

<div class="sl" bind:clientWidth={w} bind:clientHeight={h} style:--c={color}>
  {#if w > 0 && h > 0 && values.length > 1}
    <svg width={w} height={h} aria-hidden="true">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color={color} stop-opacity="0.4" />
          <stop offset="100%" stop-color={color} stop-opacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#{gid})" />
      <path d={linePath} class="sl-line" pathLength="1" style:stroke={color} />
    </svg>
  {/if}
</div>

<style>
  .sl {
    width: 100%;
    height: 100%;
    min-height: 0;
  }
  svg {
    display: block;
  }
  .sl-line {
    fill: none;
    stroke-width: 1.5;
    stroke-linecap: round;
    stroke-dasharray: 1;
    stroke-dashoffset: 1;
    animation: sl-draw 1s ease-out 0.15s forwards;
  }
  @keyframes sl-draw {
    to {
      stroke-dashoffset: 0;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .sl-line {
      animation: none;
      stroke-dashoffset: 0;
    }
  }
</style>
