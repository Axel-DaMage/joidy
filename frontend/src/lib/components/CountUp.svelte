<script lang="ts">
  import { tweenNumber } from '$lib/utils/motion';

  // Animated number: eases from the previous value to the new one. Honors
  // prefers-reduced-motion by jumping straight to the target (#1657 — the
  // count-up primitive now lives in lib/utils/motion.ts).
  let {
    value,
    duration = 700,
    format = (n: number) => Math.round(n).toLocaleString(),
  }: { value: number; duration?: number; format?: (n: number) => string } = $props();

  let shown = $state(0);
  let from = 0;

  $effect(() => {
    const target = value;
    const cancel = tweenNumber(from, target, {
      duration,
      onUpdate: (v) => {
        shown = v;
      },
    });
    return () => {
      cancel();
      from = shown;
    };
  });
</script>

{format(shown)}
