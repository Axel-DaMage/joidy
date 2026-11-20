import { writable } from 'svelte/store';
import { browser } from '$app/env';
import { api, type GraphData } from '$lib/api';
import { logger } from '$lib/utils/logger';
import { SESSION_RESET_EVENT } from './session';

export const graphData    = writable<GraphData>({ nodes: [], edges: [] });
export const graphLoading = writable(false);
export const selectedTag  = writable<number | string | null>(null);

// Drop graph state on session reset (logout / 401) — nodes embed note titles
// and tag names that must not leak to the next user (#1325).
if (browser) {
  window.addEventListener(SESSION_RESET_EVENT, () => {
    graphData.set({ nodes: [], edges: [] });
    graphLoading.set(false);
    selectedTag.set(null);
  });
}

export async function loadGraph(): Promise<void> {
  graphLoading.set(true);
  try {
    const data = await api.tags.graph();
    graphData.set(data);
  } catch (e) {
    logger.error('[graph] Failed to load:', e);
  } finally {
    graphLoading.set(false);
  }
}
