/**
 * Managed timer registry (#1003).
 *
 * Frontend timer convention — pick ONE of these per call site:
 *
 * 1. Components: create a registry (`const timers = createTimerRegistry()`)
 *    and call `timers.clearAll()` from `onDestroy`. Every `setTimeout` /
 *    `setInterval` whose callback touches component state must be registered
 *    so it cannot fire after unmount.
 * 2. Timers created inside an `$effect` should prefer the effect's cleanup
 *    return (`return () => clearTimeout(id)`): it covers both re-runs and
 *    component teardown.
 * 3. Module-level stores live for the whole app session, so their timers are
 *    not bound to a component. They are either cleared by an explicit store
 *    teardown (`stopPolling`, `stopBackgroundSync`, `clearAllToastTimers`, …)
 *    or marked inline with `// intentional: <reason>`.
 * 4. A component timer that must outlive the component — e.g. triggering
 *    `window.location.reload()`, or dispatching a `window` event after
 *    navigation — stays a raw `setTimeout` with an inline
 *    `// intentional: <reason>` comment.
 */

type TimerId = ReturnType<typeof setTimeout>;

/**
 * Creates a registry that tracks timers so they can be disposed of in one
 * call — typically from a component's `onDestroy` or an `$effect` cleanup.
 */
export function createTimerRegistry() {
  const timeouts = new Set<TimerId>();
  const intervals = new Set<TimerId>();

  return {
    /** Like `setTimeout`, but tracked. The callback is skipped once cleared. */
    timeout(fn: () => void, ms: number): TimerId {
      const id = setTimeout(() => {
        timeouts.delete(id);
        fn();
      }, ms);
      timeouts.add(id);
      return id;
    },
    /** Like `setInterval`, but tracked. Stopped by `clear()` / `clearAll()`. */
    interval(fn: () => void, ms: number): TimerId {
      const id = setInterval(fn, ms);
      intervals.add(id);
      return id;
    },
    /** Clear a single tracked timer (works for timeouts and intervals). */
    clear(id: TimerId | null | undefined): void {
      if (id === null || id === undefined) return;
      // Timeout and interval ids share the same pool in browsers, so calling
      // both clear functions is a safe no-op for whichever kind `id` is not.
      clearTimeout(id);
      clearInterval(id);
      timeouts.delete(id);
      intervals.delete(id);
    },
    /** Clear every tracked timer. Safe to call from `onDestroy`. */
    clearAll(): void {
      for (const id of timeouts) clearTimeout(id);
      for (const id of intervals) clearInterval(id);
      timeouts.clear();
      intervals.clear();
    },
    /** Number of currently tracked timers (mainly for tests). */
    get size(): number {
      return timeouts.size + intervals.size;
    },
  };
}

export type TimerRegistry = ReturnType<typeof createTimerRegistry>;
