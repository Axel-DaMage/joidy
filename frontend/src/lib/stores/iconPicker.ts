import { writable, derived } from 'svelte/store';
import { loadAllLucideIconNames } from '$lib/utils/lucideIcons';
import { logger } from '$lib/utils/logger';

// The full ~1,900-name list is fetched lazily the first time a picker opens —
// it pulls the lucide namespace as an async chunk and must stay out of the
// entry bundle (#1311).
const allIcons = writable<string[]>([]);
let loadStarted = false;
function ensureIconNames() {
  if (loadStarted) return;
  loadStarted = true;
  loadAllLucideIconNames()
    .then((names) => allIcons.set(names))
    // A failed chunk left `loadStarted` stuck true with an empty list —
    // reset so the next picker open retries (#1459).
    .catch((err) => {
      loadStarted = false;
      logger.warn('[iconPicker] lucide namespace load failed:', err);
    });
}

export function createIconPickerStore() {
  ensureIconNames();
  const searchTerm = writable('');
  const visibleLimit = writable(150);

  const filteredAll = derived([allIcons, searchTerm], ([$all, $search]) => {
    if (!$search) return $all;
    const q = $search.toLowerCase();
    return $all.filter((ic) => ic.toLowerCase().includes(q));
  });

  const visibleIcons = derived([filteredAll, visibleLimit], ([$all, $limit]) => {
    return $all.slice(0, $limit);
  });

  return {
    searchTerm,
    visibleLimit,
    visibleIcons,
    filteredAll,
    reset() {
      searchTerm.set('');
      visibleLimit.set(150);
    },
    loadMore() {
      visibleLimit.update((n) => n + 150);
    },
    handleScroll(e: Event) {
      const target = e.currentTarget as HTMLElement;
      if (target.scrollHeight - target.scrollTop - target.clientHeight < 150) {
        this.loadMore();
      }
    },
  };
}
