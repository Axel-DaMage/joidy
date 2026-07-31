import { writable, derived } from 'svelte/store';
import * as L from 'lucide-svelte';

// Get all icon names, filtering out duplicates where lucide-svelte exports
// both "X" and "XIcon" for the same icon (e.g. "File" and "FileIcon")
const _rawIcons = Object.keys(L).filter(
  (k) => /^[A-Z]/.test(k) && k !== 'default' && k !== 'createLucideIcon'
);
const _iconSet = new Set(_rawIcons);
const ALL_ICONS = _rawIcons.filter(
  (k) => !(k.endsWith('Icon') && _iconSet.has(k.slice(0, -4)))
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
