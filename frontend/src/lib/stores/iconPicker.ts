import { writable, derived } from 'svelte/store';
import * as L from 'lucide-svelte';

const ALL_ICONS = Object.keys(L).filter(
  (k) => /^[A-Z]/.test(k) && k !== 'default' && k !== 'createLucideIcon'
);

export function createIconPickerStore() {
  const searchTerm = writable('');
  const visibleLimit = writable(150);

  const filteredAll = derived(searchTerm, ($search) => {
    if (!$search) return ALL_ICONS;
    const q = $search.toLowerCase();
    return ALL_ICONS.filter((ic) => ic.toLowerCase().includes(q));
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
    }
  };
}
