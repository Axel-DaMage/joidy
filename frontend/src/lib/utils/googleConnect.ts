/**
 * Shared Google OAuth connect flow (#43).
 *
 * The consent URL is opened in a popup; the callback persists tokens
 * server-side, so the caller polls a readiness check until the needed
 * capability is live (same pattern as SettingsGoogle's inline flow, factored
 * out so the contacts page and SettingsContacts share it).
 */
import { api } from '$lib/api';

export type GoogleConnectResult = 'connected' | 'timeout' | 'error' | 'cancelled';

export interface GoogleConnectOptions {
  /**
   * Persist OAuth credentials BEFORE opening the consent window — the
   * /auth endpoint reads them from settings, and an unsaved form would 400
   * (#1148). Optional: env-configured installs skip it.
   */
  persistCredentials?: () => Promise<void>;
  /**
   * Poll target — resolves true once the account has the capability the
   * caller needs (e.g. contacts read scope). Called every poll interval.
   */
  isReady: () => Promise<boolean>;
  /** Consent URL fetcher — defaults to the shared Google OAuth endpoint. */
  getAuthUrl?: () => Promise<{ url: string }>;
  /** Total wait budget (default 5 min, same as SettingsGoogle). */
  timeoutMs?: number;
  /** Poll interval (default 3s). */
  pollMs?: number;
}

export interface GoogleConnectHandle {
  /** Resolves with the final outcome ('cancelled' when cancel() is called). */
  done: Promise<GoogleConnectResult>;
  /** Stop polling and settle `done` (call on component destroy). */
  cancel: () => void;
}

export function startGoogleConnect(opts: GoogleConnectOptions): GoogleConnectHandle {
  const timeoutMs = opts.timeoutMs ?? 300_000;
  const pollMs = opts.pollMs ?? 3_000;

  let interval: ReturnType<typeof setInterval> | null = null;
  let timeout: ReturnType<typeof setTimeout> | null = null;
  let settled = false;

  function cleanup() {
    if (interval) {
      clearInterval(interval);
      interval = null;
    }
    if (timeout) {
      clearTimeout(timeout);
      timeout = null;
    }
  }

  let settle!: (result: GoogleConnectResult) => void;
  const done = new Promise<GoogleConnectResult>((resolve) => {
    settle = (result) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(result);
    };
  });

  void (async () => {
    try {
      await opts.persistCredentials?.();
      const data = await (opts.getAuthUrl ?? (() => api.google.authUrl()))();
      window.open(data.url, '_blank', 'noopener,noreferrer');
    } catch {
      settle('error');
      return;
    }

    interval = setInterval(() => {
      void (async () => {
        try {
          if (await opts.isReady()) settle('connected');
        } catch {
          /* transient poll failure — keep polling */
        }
      })();
    }, pollMs);

    timeout = setTimeout(() => settle('timeout'), timeoutMs);
  })();

  return {
    done,
    cancel: () => settle('cancelled'),
  };
}
