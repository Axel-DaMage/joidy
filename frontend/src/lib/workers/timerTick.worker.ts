// Timer tick worker (#969).
//
// Main-thread setInterval is throttled to ~1/min in backgrounded tabs, which
// would freeze countdowns and delay alarms. Worker timers are not throttled,
// so this worker emits a steady tick; the main thread derives all remaining
// times from absolute Date.now() timestamps, which makes drift impossible
// even if a tick arrives late.

interface TickMessage {
  type: 'tick';
  now: number;
}

const scope = self as unknown as {
  onmessage: ((e: MessageEvent<'start' | 'stop'>) => void) | null;
  postMessage: (msg: TickMessage) => void;
};

const TICK_MS = 250;
let interval: ReturnType<typeof setInterval> | null = null;

scope.onmessage = (e: MessageEvent<'start' | 'stop'>) => {
  if (e.data === 'start') {
    if (interval) return;
    interval = setInterval(() => {
      scope.postMessage({ type: 'tick', now: Date.now() });
    }, TICK_MS);
  } else if (e.data === 'stop' && interval) {
    clearInterval(interval);
    interval = null;
  }
};
