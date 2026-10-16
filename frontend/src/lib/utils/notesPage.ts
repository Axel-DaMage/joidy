// Shared actions/logic for the notes page, extracted from
// routes/notes/+page.svelte (#210).
import { get } from 'svelte/store';
import { goto } from '$app/navigation';
import { page } from '$app/stores';
import { api, type Note } from '$lib/api';
import { logger } from '$lib/utils/logger';
import { DEFAULT_GOAL_COLOR } from '$lib/utils/goalColors';
import { extractFrontmatter, getFileIcon, type SortMode } from '$lib/utils/fileTree';
import { updateFolderMeta } from '$lib/stores/settings';
import { patchUserSettings, loadUserSettings } from '$lib/utils/userSettings';
import { captureSnapshot } from '$lib/stores/pageSnapshots';
import {
  notes,
  loadNotes,
  createNote,
  updateNote,
  deleteNote,
  deleteSelectedNotes,
  aiSuggestions,
  selectedNoteIds,
  hasMoreNotes,
  loadingMore,
  loadMore,
} from '$lib/stores/notes';
import * as ui from '$lib/stores/notesUi';

export function ensureNoteEditor() {
  if (!get(ui.NoteEditorComp)) {
    import('$lib/components/NoteEditor.svelte').then((m) => ui.NoteEditorComp.set(m.default));
  }
}

export function getNoteVisual(note: Note) {
  const fm = extractFrontmatter(note.content || '');
  return {
    icon: fm.icon || getFileIcon(note.title, note.content || ''),
    color: fm.color || undefined,
    pack: fm.pack || undefined,
  };
}

export function normalizeVaultFolder(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
}

export function buildDailySourcePath(vaultPath: string, folder: string, fileName: string): string {
  const cleanVault = vaultPath.replace(/[\\/]+$/, '');
  const cleanFolder = normalizeVaultFolder(folder);
  return `${cleanVault}/${cleanFolder}/${fileName}`;
}

export function openSettingsForDaily() {
  window.dispatchEvent(new CustomEvent('joidy:open-settings'));
}

// ── Navigation history ──
export async function addToHistory(id: number) {
  if (get(ui.isNavigatingHistory)) return;
  const stack = get(ui.historyStack);
  const index = get(ui.historyIndex);

  // Check if we are just moving to an adjacent item (e.g. browser back/forward)
  if (index > 0 && stack[index - 1] === id) {
    ui.historyIndex.set(index - 1);
    return;
  }
  if (index >= 0 && index < stack.length - 1 && stack[index + 1] === id) {
    ui.historyIndex.set(index + 1);
    return;
  }

  // If it's the same as current, do nothing
  if (index >= 0 && stack[index] === id) return;

  // New branch: clear forward history and push
  const newStack = stack.slice(0, index + 1);
  const next = [...newStack, id].slice(-50);
  ui.historyStack.set(next);
  ui.historyIndex.set(next.length - 1);
}

async function navigateHistory(delta: -1 | 1) {
  const stack = get(ui.historyStack);
  const index = get(ui.historyIndex);
  const target = index + delta;
  if (target < 0 || target >= stack.length) return;
  ui.isNavigatingHistory.set(true);
  ui.historyIndex.set(target);
  const id = stack[target];
  const n = get(notes).find((n) => n.id === id);
  if (n) await openNote(n);
  ui.isNavigatingHistory.set(false);
}

export const goToPrev = () => navigateHistory(-1);
export const goToNext = () => navigateHistory(1);

// ── Note actions ──
export async function openNote(note: Note) {
  const selectedId = get(page).url.searchParams.get('id');
  if (selectedId !== String(note.id)) {
    goto(`/notes?id=${note.id}`, { keepFocus: true, noScroll: true });
  }
  ui.selectedNote.set(note);
  addToHistory(note.id);
  ui.showEditor.set(true);
  ui.editingNew.set(false);
  aiSuggestions.set([]);
  ensureNoteEditor();

  // Notes fetched via list_notes have content deferred (content: "").
  // Fetch full note content if empty or to ensure freshness.
  const noteId = note.id;
  ui.loadingNoteContent.set(true);
  try {
    const fullNote = await api.notes.get(noteId);
    // Ensure the user hasn't switched to another note while fetching
    if (get(ui.selectedNote)?.id === noteId) {
      ui.selectedNote.set(fullNote);
      notes.update((ns) => ns.map((n) => (n.id === noteId ? fullNote : n)));
    }
  } catch (e) {
    logger.error('[notes] Failed to load note details:', e);
  } finally {
    if (get(ui.selectedNote)?.id === noteId) {
      ui.loadingNoteContent.set(false);
    }
  }
}

export function openNew(folderPath?: string) {
  ui.selectedNote.set(null);
  ui.showEditor.set(true);
  ui.editingNew.set(true);
  ui.isMomentary.set(false);
  ui.dailySourcePath.set(null);
  ui.newNoteFolderPath.set(folderPath ?? null);
  ui.dailyInitialTitle.set('');
  aiSuggestions.set([]);
  ensureNoteEditor();
}

export function openMomentary() {
  ui.selectedNote.set(null);
  ui.showEditor.set(true);
  ui.editingNew.set(true);
  ui.isMomentary.set(true);
  ui.dailySourcePath.set(null);
  ui.newNoteFolderPath.set(null);
  ui.dailyInitialTitle.set('');
  ensureNoteEditor();
}

export async function openDaily() {
  if (!get(ui.dailyNotesConfigured)) {
    openSettingsForDaily();
    return;
  }

  const config = await api.config.get();

  const vaultPathVal = (config.obsidian_vault_path || '').trim();
  const dailyFolder = (config.daily_notes_folder || '').trim();

  if (!vaultPathVal || !dailyFolder) return;

  const today = new Date().toISOString().split('T')[0];
  ui.selectedNote.set(null);
  ui.showEditor.set(true);
  ui.editingNew.set(true);
  ui.isMomentary.set(false); // Usually daily notes are real
  ui.dailyInitialTitle.set(today);
  ui.dailySourcePath.set(buildDailySourcePath(vaultPathVal, dailyFolder, `${today}.md`));
  ui.newNoteFolderPath.set(null);
  aiSuggestions.set([]);
  ensureNoteEditor();
}

export function closeEditor() {
  ui.showEditor.set(false);
  ui.selectedNote.set(null);
  ui.loadingNoteContent.set(false);
  ui.dailySourcePath.set(null);
  ui.newNoteFolderPath.set(null);
  ui.dailyInitialTitle.set('');
  goto('/notes');
}

export async function handleSave(
  e: CustomEvent<{ title: string; content: string; tags: string[] }>
) {
  const { title, content, tags } = e.detail;
  if (get(ui.isMomentary)) {
    ui.momentaryDraft.set({ title, content, tags });
    return;
  }
  if (get(ui.editingNew)) {
    const dsp = get(ui.dailySourcePath);
    const dit = get(ui.dailyInitialTitle);
    if (dit && !dsp) return;
    let sp = dsp;
    const folder = get(ui.newNoteFolderPath);
    if (!sp && folder && title.trim()) {
      sp = buildDailySourcePath(get(ui.vaultPath) || '/vault', folder, `${title.trim()}.md`);
    }
    const n = await createNote(title, content, tags, sp);
    if (n) {
      ui.selectedNote.set(n);
      ui.editingNew.set(false);
    }
  } else {
    const sel = get(ui.selectedNote);
    if (sel) {
      await updateNote(sel.id, { title, content, tags });
    }
  }
}

export async function handleDelete() {
  ui.deleteMode.set('single');
  ui.deleteModalOpen.set(true);
}

export async function confirmDelete() {
  const mode = get(ui.deleteMode);
  if (mode === 'bulk') {
    deleteSelectedNotes();
  } else if (mode === 'ctx') {
    const id = get(ui.deleteCtxNoteId);
    if (id !== null) {
      await deleteNote(id);
      ui.deleteCtxNoteId.set(null);
    }
  } else {
    const sel = get(ui.selectedNote);
    if (mode === 'single' && sel) {
      await deleteNote(sel.id);
      closeEditor();
    }
  }
  ui.deleteModalOpen.set(false);
}

export function quickNoteFromScratch() {
  openNew();
  // We can't easily pre-fill NoteEditor here without more store logic,
  // but the user just wants the "normal" creation flow to be the priority.
}

// ── Vault folders / tree ──
export async function loadFolders() {
  try {
    const res = await api.folders.list();
    ui.vaultFolders.set(res.folders);
  } catch (e) {
    logger.warn('[notes] Failed to load vault folders:', e);
  }
}

export async function refreshTree() {
  try {
    const [ns, fs] = await Promise.all([api.notes.list(), api.folders.list()]);
    notes.set(ns);
    ui.vaultFolders.set(fs.folders);
  } catch (e) {
    logger.error('[notes] Failed to refresh tree:', e);
  }
}

// ── Context menu & folder modals ──
export function handleContextMenu(e: MouseEvent, node: import('$lib/utils/fileTree').FlatNode) {
  e.preventDefault();
  e.stopPropagation();
  ui.ctxMenu.set({ x: e.clientX, y: e.clientY, node });
}

export function handleRename() {
  const menu = get(ui.ctxMenu);
  if (!menu) return;
  ui.renamingNode.set(menu.node);
  ui.renameValue.set(menu.node.name);
  ui.ctxMenu.set(null);
}

export async function confirmRename() {
  const node = get(ui.renamingNode);
  const value = get(ui.renameValue);
  if (!node || !value.trim()) {
    ui.renamingNode.set(null);
    return;
  }
  ui.renamingNode.set(null);
  if (node.type === 'file' && node.note) {
    await updateNote(node.note.id, { title: value.trim() });
  }
}

export function handleMove() {
  const menu = get(ui.ctxMenu);
  if (!menu) return;
  ui.movingNode.set(menu.node);
  ui.ctxMenu.set(null);
}

export async function confirmMove(targetPath: string) {
  const node = get(ui.movingNode);
  if (!node || !node.note) {
    ui.movingNode.set(null);
    return;
  }
  const note = node.note;
  ui.movingNode.set(null);
  const newPath = targetPath ? `${targetPath}/${node.name}` : node.name;
  await api.notes.update(note.id, { source_path: newPath });
  await loadNotes();
}

export function handleDeleteNote() {
  const menu = get(ui.ctxMenu);
  if (!menu || !menu.node.note) {
    ui.ctxMenu.set(null);
    return;
  }
  const note = menu.node.note;
  ui.ctxMenu.set(null);
  ui.deleteMode.set('ctx');
  ui.deleteCtxNoteId.set(note.id);
  ui.deleteModalOpen.set(true);
}

export function handleNewNoteInFolder() {
  const menu = get(ui.ctxMenu);
  if (!menu) return;
  const path = menu.node.path;
  ui.ctxMenu.set(null);
  openNew(path);
}

export function handleDeleteFolder() {
  const menu = get(ui.ctxMenu);
  if (!menu) return;
  const path = menu.node.path;
  ui.ctxMenu.set(null);
  if (confirm(`¿Eliminar carpeta "${menu.node.name}" y todas sus notas?`)) {
    // Delete notes in this folder
    const ids = get(notes)
      .filter((n) => n.source_path && n.source_path.includes(path))
      .map((n) => n.id);
    Promise.all(ids.map((id) => deleteNote(id)))
      .then(async () => {
        try {
          await api.folders.delete(path);
        } catch (e) {
          logger.warn('[notes] Failed to delete folder on disk:', e);
        }
        await refreshTree();
      })
      .catch((e) => logger.error('[notes] Failed to delete folder notes:', e));
  }
}

export async function openFolderCustomizer(node: {
  path: string;
  color?: string | null;
  icon?: string | null;
  note?: Note;
}) {
  ui.editingFolder.set(node.path);
  ui.folderColor.set(node.color || DEFAULT_GOAL_COLOR);
  ui.folderIcon.set(node.icon || 'Folder');
  ui.editingFolderNote.set(node.note || null);
}

export function handleCreateFolder() {
  ui.creatingFolder.set(true);
  ui.newFolderName.set('');
  ui.newFolderParent.set('');
  ui.newFolderIcon.set('Folder');
  ui.newFolderColor.set(DEFAULT_GOAL_COLOR);
}

// ── Preferences persistence ──
// itemCount/currentScroll are provided by the caller (the sidebar owns the
// list's scroll position). Mirrors the original page-local persistNotesPrefs.
export function persistNotesPrefs(itemCount: number, currentScroll: number) {
  const treeTop = get(ui.__treeScrollTop);
  const listTop = get(ui.__listScrollTop);
  const vm = get(ui.viewMode);
  const nextTreeScrollTop = vm === 'tree' ? currentScroll : treeTop;
  const nextListScrollTop = vm === 'list' ? currentScroll : listTop;
  ui.__treeScrollTop.set(nextTreeScrollTop);
  ui.__listScrollTop.set(nextListScrollTop);

  patchUserSettings({
    notesUi: {
      panelWidth: get(ui.panelWidth),
      sortMode: get(ui.sortMode),
      viewMode: vm,
      allCollapsed: get(ui.allCollapsed),
      collapsedPaths: Array.from(get(ui.collapsed)),
      search: get(ui.search),
      selectedNoteId: get(ui.selectedNote)?.id ?? null,
      treeScrollTop: nextTreeScrollTop,
      listScrollTop: nextListScrollTop,
    },
  });
}

export function captureNotesSnapshot() {
  // Scroll position is persisted via onListScroll/onVirtualScrollChange
  // → persistNotesPrefs → localStorage. No need to capture it in the
  // snapshot (which is stale in SPA navigation anyway).
  captureSnapshot(
    '/notes',
    {
      search: get(ui.search),
      viewMode: get(ui.viewMode),
      sortMode: get(ui.sortMode),
      allCollapsed: get(ui.allCollapsed),
      collapsedPaths: Array.from(get(ui.collapsed)),
      selectedNoteId: get(ui.selectedNote)?.id,
    },
    []
  );
}

export const SORT_MODES: SortMode[] = [
  'az',
  'za',
  'edit-new',
  'edit-old',
  'create-new',
  'create-old',
];

export function isSortMode(value: unknown): value is SortMode {
  return typeof value === 'string' && SORT_MODES.includes(value as SortMode);
}

// ── List scroll & persistence helpers (sidebar list body owns the DOM el via
// the listScrollEl store). ──
export function currentItemCount() {
  return get(ui.viewMode) === 'tree' ? get(ui.flatNodes).length : get(ui.filtered).length;
}

function currentScroll() {
  return currentItemCount() > 50
    ? get(ui.virtualScrollTop)
    : (get(ui.listScrollEl)?.scrollTop ?? 0);
}

export function persist() {
  persistNotesPrefs(currentItemCount(), currentScroll());
}

export function setSortMode(mode: SortMode) {
  ui.sortMode.set(mode);
  if (get(ui.notesPrefsReady)) persist();
}

export function toggleCollapseAll() {
  const next = !get(ui.allCollapsed);
  ui.allCollapsed.set(next);
  if (next) {
    const folders = get(ui.flatNodes).filter((n) => n.type === 'folder');
    const nextSet = new Set(get(ui.collapsed));
    for (const f of folders) nextSet.add(f.path);
    ui.collapsed.set(nextSet);
  } else {
    ui.collapsed.set(new Set());
  }
  if (get(ui.notesPrefsReady)) persist();
}

export function toggleFolder(path: string) {
  const nextSet = new Set(get(ui.collapsed));
  if (nextSet.has(path)) nextSet.delete(path);
  else nextSet.add(path);
  ui.collapsed.set(nextSet);
  if (get(ui.notesPrefsReady)) persist();
}

export function onListScroll() {
  const el = get(ui.listScrollEl);
  if (!get(ui.notesPrefsReady) || !el) return;
  // When VirtualList is used (>50 items), the outer .list-scroll container
  // doesn't scroll — VirtualList has its own internal scroll container.
  if (currentItemCount() > 50) return;
  if (get(ui.viewMode) === 'tree') ui.__treeScrollTop.set(el.scrollTop);
  else ui.__listScrollTop.set(el.scrollTop);
  persist();
  // Infinite scroll for non-virtualized list mode.
  maybeLoadMore();
}

// Infinite scroll: load next page when the user is near the bottom.
export function maybeLoadMore() {
  if (get(ui.viewMode) !== 'list' || get(ui.search) || get(loadingMore) || !get(hasMoreNotes))
    return;
  const el = get(ui.listScrollEl);
  if (el) {
    const { scrollTop, scrollHeight, clientHeight } = el;
    if (scrollHeight - scrollTop - clientHeight < 300) {
      loadMore();
    }
  }
}

export function handleNearBottom() {
  if (get(ui.viewMode) !== 'list' || get(ui.search) || get(loadingMore) || !get(hasMoreNotes))
    return;
  loadMore();
}

// Called by VirtualList when its internal scroll position changes.
export function onVirtualScrollChange(scrollVal: number) {
  if (!get(ui.notesPrefsReady)) return;
  ui.virtualScrollTop.set(scrollVal);
  if (get(ui.viewMode) === 'tree') ui.__treeScrollTop.set(scrollVal);
  else ui.__listScrollTop.set(scrollVal);
  persist();
}
