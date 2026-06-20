import { onMount, onDestroy } from 'svelte';

export function useVisibilityChange(
  onVisible: () => void,
  onHidden: () => void
) {
  function handleVisibilityChange() {
    if (document.visibilityState === 'visible') {
      onVisible();
    } else if (document.visibilityState === 'hidden') {
      onHidden();
    }
  }

  onMount(() => {
    document.addEventListener('visibilitychange', handleVisibilityChange);
  });

  onDestroy(() => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
  });
}

export function useInterval(callback: () => void, delay: number) {
  let intervalId: ReturnType<typeof setInterval> | null = null;

  onMount(() => {
    intervalId = setInterval(callback, delay);
  });

  onDestroy(() => {
    if (intervalId) clearInterval(intervalId);
  });
}

export function useTimeout(callback: () => void, delay: number) {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  onMount(() => {
    timeoutId = setTimeout(callback, delay);
  });

  onDestroy(() => {
    if (timeoutId) clearTimeout(timeoutId);
  });
}