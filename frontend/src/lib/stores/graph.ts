import { writable } from 'svelte/store';
import { api, type GraphData } from '$lib/api';

export const graphData    = writable<GraphData>({ nodes: [], edges: [] });
export const graphLoading = writable(false);
export const selectedTag  = writable<number | null>(null);

export async function loadGraph(): Promise<void> {
  graphLoading.set(true);
  try {
    const data = await api.tags.graph();
    graphData.set(data);
  } catch (e) {
    console.error('[graph] Failed to load:', e);
  } finally {
    graphLoading.set(false);
  }
}
