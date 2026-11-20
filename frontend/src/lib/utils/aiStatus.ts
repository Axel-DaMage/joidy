// AI status pill mapping (#1460).
//
// `GET /ai/usage` grew two fields on the backend: `ai_status`
// ("ok" | "degraded" | "unavailable" | "disabled") and `ai_status_detail`.
// When the fields are absent (older backend) the pill falls back to the
// previous env-flag behaviour (`ai_enabled` → ok/disabled).

export type AiStatus = 'ok' | 'degraded' | 'unavailable' | 'disabled';
export type AiStatusView = AiStatus | 'checking';

export interface AiUsageLike {
  ai_enabled: boolean;
  ai_status?: string | null;
  ai_status_detail?: string | null;
}

const KNOWN_STATUSES: readonly AiStatus[] = ['ok', 'degraded', 'unavailable', 'disabled'];

/**
 * Resolve the effective pill status from the `/ai/usage` payload.
 * `null`/`undefined` usage maps to 'checking' (fetch still in flight or
 * failed), an unrecognised `ai_status` degrades to the `ai_enabled`
 * fallback for backward compatibility.
 */
export function aiStatusFromUsage(usage: AiUsageLike | null | undefined): AiStatusView {
  if (usage == null) return 'checking';
  const status = usage.ai_status;
  if (status && (KNOWN_STATUSES as readonly string[]).includes(status)) {
    return status as AiStatus;
  }
  return usage.ai_enabled ? 'ok' : 'disabled';
}
