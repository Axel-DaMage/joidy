// Formatters live in the module that owns their domain — do not re-add
// generic duplicates here:
//   - durations (ms):  $lib/utils/spotify.ts     → formatDuration
//   - durations (s):   $lib/strava/format.ts    → formatDuration
//   - byte sizes:      $lib/utils/gmail.ts      → formatBytes

/**
 * Returns a human-readable display name for a tag.
 * Tags whose name is a bare hex color code (e.g. "ef4444", "c8a96e") are
 * replaced with a fallback label so the UI never shows a raw color code (#260).
 */
export function displayTagName(name: string | undefined | null): string {
  if (!name) return 'Sin nombre';
  if (/^[0-9a-f]{6}$/.test(name)) return 'Sin nombre';
  return name;
}
