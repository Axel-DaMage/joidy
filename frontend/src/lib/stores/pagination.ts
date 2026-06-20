import { writable, derived } from 'svelte/store';

export interface PaginationState {
  page: number;
  perPage: number;
  total: number;
}

export function createPaginationStore(initialPerPage = 10) {
  const state = writable<PaginationState>({
    page: 1,
    perPage: initialPerPage,
    total: 0,
  });

  const setTotal = (total: number) => state.update(s => ({ ...s, total }));
  const setPage = (page: number) => state.update(s => ({ ...s, page }));
  const setPerPage = (perPage: number) => state.update(s => ({ ...s, perPage, page: 1 }));
  const nextPage = () => state.update(s => ({ ...s, page: s.page + 1 }));
  const prevPage = () => state.update(s => ({ ...s, page: Math.max(1, s.page - 1) }));
  const reset = () => state.update(s => ({ ...s, page: 1 }));

  const totalPages = derived(state, $s => Math.ceil($s.total / $s.perPage));
  const hasNext = derived(state, $s => $s.page < Math.ceil($s.total / $s.perPage));
  const hasPrev = derived(state, $s => $s.page > 1);
  const offset = derived(state, $s => ($s.page - 1) * $s.perPage);

  return {
    state,
    setTotal,
    setPage,
    setPerPage,
    nextPage,
    prevPage,
    reset,
    totalPages,
    hasNext,
    hasPrev,
    offset,
  };
}

export function paginate<T>(items: T[], page: number, perPage: number): T[] {
  const start = (page - 1) * perPage;
  return items.slice(start, start + perPage);
}