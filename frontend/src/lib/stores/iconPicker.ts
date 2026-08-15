import { writable, derived } from 'svelte/store';
import { ALL_LUCIDE_ICON_NAMES } from '$lib/utils/lucideIcons';

// Icon names come from `import.meta.glob` over lucide-svelte's icon files, so
// no icon code is imported just to enumerate names (see #209).
const ALL_ICONS = ALL_LUCIDE_ICON_NAMES;

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
    },
  };
}
