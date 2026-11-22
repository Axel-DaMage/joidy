// Tracks an in-flight vault-sync burst so the WS handler in +layout.svelte can
// collapse per-file toasts and XP pings into a single summary emission (#1500).
// A bulk resync emits ≥2–3 WS messages per file; one toast per message pays a
// full notifications.update + Toast re-render + aria-atomic announcement on the
// main thread each — enough contiguous work to freeze the tab mid-sync.
export interface VaultSyncSummary {
  files: number;
  xp: number;
}

export function createVaultSyncBurst() {
  let files = 0;
  let xp = 0;
  return {
    /** Returns the running file count — 1 marks the first file of a burst. */
    recordFile(): number {
      return ++files;
    },
    recordXp(amount: number): void {
      xp += amount;
    },
    get fileCount(): number {
      return files;
    },
    /** Read-and-clear: returns the accumulated totals and zeroes the tracker. */
    reset(): VaultSyncSummary {
      const summary = { files, xp };
      files = 0;
      xp = 0;
      return summary;
    },
  };
}
