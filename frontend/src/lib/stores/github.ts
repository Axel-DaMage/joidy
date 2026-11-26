/**
 * Shared GitHub connection status (#1545).
 *
 * `GET /integrations/github/status` is probed by the always-mounted status
 * bar pill and again by the dashboard widget on every load — not always
 * concurrently, so the api.ts in-flight GET dedup can't merge them. This
 * funnels all consumers through a single in-flight/short-TTL-cached request.
 * Requests run silent: each caller already maps failures to its own UI
 * state, and a degraded integration must not toast on every dashboard load.
 */
import { browser } from '$app/env';
import { api } from '$lib/api';
import { SESSION_RESET_EVENT } from './session';

export interface GithubStatus {
  connected: boolean;
  username: string | null;
}

const STATUS_TTL_MS = 60_000;

let cached: { data: GithubStatus; ts: number } | null = null;
let inflight: Promise<GithubStatus> | null = null;

// The status is user-scoped — drop it on session reset like every other
// user-data cache (#1305 pattern), so a re-login can't inherit it stale.
if (browser) {
  window.addEventListener(SESSION_RESET_EVENT, () => {
    cached = null;
  });
}

/** Fetch the GitHub connection status, sharing one in-flight request and a
 * 60s result cache across consumers. `force` bypasses the cache — required
 * for flows that must observe a just-changed state (connect/disconnect in
 * the Settings panel). */
export function getGithubStatus(force = false): Promise<GithubStatus> {
  if (!force && cached && Date.now() - cached.ts < STATUS_TTL_MS) {
    return Promise.resolve(cached.data);
  }
  if (!inflight) {
    inflight = api.github
      .status({ silent: true })
      .then((status) => {
        cached = { data: status, ts: Date.now() };
        return status;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}
