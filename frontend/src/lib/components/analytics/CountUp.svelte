<script lang="ts">
  // Animated number: eases from the previous value to the new one. Honors
  // prefers-reduced-motion by jumping straight to the target.
  let {
    value,
    duration = 700,
    format = (n: number) => Math.round(n).toLocaleString(),
  }: { value: number; duration?: number; format?: (n: number) => string } = $props();

  let shown = $state(0);
  let from = 0;

  $effect(() => {
    const target = value;
    const reduce =
      typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce || duration <= 0) {
      shown = target;
      from = target;
      return;
    }
    const start = performance.now();
    const origin = from;
    let raf = requestAnimationFrame(function tick(now) {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      shown = origin + (target - origin) * eased;
      if (p < 1) raf = requestAnimationFrame(tick);
      else from = target;
    });
    return () => {
      cancelAnimationFrame(raf);
      from = shown;
    };
  });
</script>

{format(shown)}
