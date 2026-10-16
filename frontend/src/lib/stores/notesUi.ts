// Shared UI state for the notes page, extracted from routes/notes/+page.svelte
// (#210) so the sidebar, overlays and editor panel components can share it
// without prop drilling.
import { writable, derived } from 'svelte/store';
import type { Note } from '$lib/api';
import type { SortMode } from '$lib/utils/fileTree';
import { buildTree, flattenTree, type FlatNode } from '$lib/utils/fileTree';
import { notes } from '$lib/stores/notes';
import { showTrash, showHiddenFiles, folderMetaStore } from '$lib/stores/settings';

export const search = writable('');
export const selectedNote = writable<Note | null>(null);
export const loadingNoteContent = writable(false);
export const showEditor = writable(false);
export const editingNew = writable(false);
export const isMomentary = writable(false);
export const momentaryDraft = writable<{ title: string; content: string; tags: string[] }>({
  title: 'Borrador Efímero',
  content: '',
  tags: [],
});
export const dailySourcePath = writable<string | null>(null);
export const dailyInitialTitle = writable('');
export const dailyNotesConfigured = writable(false);
export const newNoteFolderPath = writable<string | null>(null);
export const deleteModalOpen = writable(false);
export const deleteMode = writable<'single' | 'bulk' | 'ctx'>('single');
export const deleteCtxNoteId = writable<number | null>(null);
export const vaultFolders = writable<string[]>([]);
export const vaultPath = writable('');
export const totalNotes = writable(0);
export const collapsed = writable<Set<string>>(new Set());
export const viewMode = writable<'tree' | 'list'>('tree');
export const sortMode = writable<SortMode>('edit-new');
export const allCollapsed = writable(false);
export const panelWidth = writable(260);
export const notesPrefsReady = writable(false);

// NoteEditor is lazy-loaded (see #347) — the component class lives in a store so
// the loader can be shared between the page and the editor panel.
export const NoteEditorComp = writable<
  typeof import('$lib/components/NoteEditor.svelte').default | null
>(null);

export const editorNote = derived(
  [editingNew, isMomentary, momentaryDraft, selectedNote],
  ([$editingNew, $isMomentary, $momentaryDraft, $selectedNote]) =>
    $editingNew
      ? $isMomentary
        ? ({ ...$momentaryDraft, id: -1, source: 'momentary' } as Note)
        : null
      : $selectedNote
);

// ── Tree overlay/modal state ──
export const ctxMenu = writable<{ x: number; y: number; node: FlatNode } | null>(null);
export const renamingNode = writable<FlatNode | null>(null);
export const renameValue = writable('');
export const movingNode = writable<FlatNode | null>(null);
export const editingFolder = writable<string | null>(null);
export const folderColor = writable('');
export const folderIcon = writable('Folder');
export const editingFolderNote = writable<Note | null>(null);
export const creatingFolder = writable(false);
export const newFolderName = writable('');
export const newFolderParent = writable('');
export const newFolderIcon = writable('Folder');
export const newFolderColor = writable('');

// Internal scroll/positions shared between the page (prefs persist) and the
// sidebar (list scroll owner). Underscore-prefixed = not part of the public API.
export const __treeScrollTop = writable(0);
export const __listScrollTop = writable(0);
export const __itemCount = writable(0);
export const __currentScroll = writable(0);
export const scrollReady = writable(false);
export const listScrollEl = writable<HTMLDivElement | null>(null);
export const virtualScrollTop = writable(0);

// Derived tree/list data (moved from the page's reactive block, #210).
export const filtered = derived([notes, search], ([$notes, $search]) =>
  $notes.filter(
    (n) =>
      !$search ||
      n.title.toLowerCase().includes($search.toLowerCase()) ||
      n.tags.some((t) => t.includes($search.toLowerCase()))
  )
);

export const tree = derived(
  [notes, viewMode, search, showTrash, showHiddenFiles, sortMode, folderMetaStore, vaultFolders],
  ([
    $notes,
    $viewMode,
    $search,
    $showTrash,
    $showHiddenFiles,
    $sortMode,
    $folderMetaStore,
    $vaultFolders,
  ]) =>
    buildTree(
      $notes,
      $viewMode === 'tree' ? $search : '',
      $showTrash,
      $showHiddenFiles,
      $sortMode,
      $folderMetaStore,
      $vaultFolders
    )
);

export const flatNodes = derived([tree, collapsed], ([$tree, $collapsed]) =>
  flattenTree($tree, $collapsed)
);

// ── Navigation history ──
export const historyStack = writable<number[]>([]);
export const historyIndex = writable(-1);
export const isNavigatingHistory = writable(false);
export const hasPrev = derived(historyIndex, (i) => i > 0);
export const hasNext = derived([historyIndex, historyStack], ([i, stack]) => i < stack.length - 1);
