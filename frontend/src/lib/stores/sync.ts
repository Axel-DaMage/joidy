import { writable } from 'svelte/store';
import { api } from '$lib/api';
import { showNotification } from './notifications';

export interface SyncConflict {
  note_id: number;
  title: string;
  source_path: string;
  local_mtime: string | null;
  remote_mtime: string | null;
  last_synced_at: string | null;
}

export type ConflictResolution = 'keep_local' | 'keep_remote' | 'merge';

interface SyncState {
  conflicts: SyncConflict[];
  loading: boolean;
  lastChecked: number | null;
  /** Note IDs the user has skipped this session — prevents the modal
   *  from re-opening on every navigation (#550 regression). */
  dismissed: Set<number>;
}

const POLL_INTERVAL = 30_000; // 30 seconds

function createSyncStore() {
  const { subscribe, set, update } = writable<SyncState>({
    conflicts: [],
    loading: false,
    lastChecked: null,
    dismissed: new Set(),
  });

  let pollTimer: ReturnType<typeof setInterval> | null = null;

  async function checkConflicts(): Promise<void> {
    update(s => ({ ...s, loading: true }));
    try {
      const data = await api.sync.conflicts();
      update(s => ({
        ...s,
        conflicts: data.conflicts,
        loading: false,
        lastChecked: Date.now(),
      }));

      if (data.conflicts.length > 0) {
        showNotification(
          `${data.conflicts.length} conflicto(s) de sincronización pendiente(s)`,
          'info'
        );
      }
    } catch {
      update(s => ({ ...s, loading: false }));
    }
  }

  async function resolveConflict(
    noteId: number,
    resolution: ConflictResolution,
    mergedContent?: string
  ): Promise<boolean> {
    try {
      await api.sync.resolve(noteId, resolution, mergedContent);
      update(s => ({
        ...s,
        conflicts: s.conflicts.filter(c => c.note_id !== noteId),
      }));
      showNotification('Conflicto resuelto', 'success');
      return true;
    } catch {
      showNotification('Error al resolver conflicto', 'error');
      return false;
    }
  }

  function startPolling(): void {
    if (pollTimer) return;
    checkConflicts();
    pollTimer = setInterval(checkConflicts, POLL_INTERVAL);
  }

  function stopPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  /** Mark a conflict as dismissed so the modal doesn't re-open on
   *  subsequent navigations within the same session (#550). */
  function dismissConflict(noteId: number): void {
    update(s => ({
      ...s,
      dismissed: new Set([...s.dismissed, noteId]),
    }));
  }

  return {
    subscribe,
    checkConflicts,
    resolveConflict,
    dismissConflict,
    startPolling,
    stopPolling,
    reset: () => set({ conflicts: [], loading: false, lastChecked: null, dismissed: new Set() }),
  };
}

export const syncStore = createSyncStore();
