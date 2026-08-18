<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    Search,
    Plus,
    X,
    List,
    FolderTree,
    ChevronRight,
    FilePen,
    FolderPlus,
    ChevronsUpDown,
    ArrowUpDown,
    Settings,
    SquareCheckBig,
  } from 'lucide-svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';

  // Lazy-load the heavy NoteEditor (1631 lines, pulls in highlight.js, marked,
  // dompurify, tiptap) so it is split into a separate chunk and only
  // downloaded when the user actually opens a note for editing (#347).
  let NoteEditor: typeof import('$lib/components/NoteEditor.svelte').default | null = null;
  function ensureNoteEditor() {
    if (!NoteEditor) {
      import('$lib/components/NoteEditor.svelte').then((m) => (NoteEditor = m.default));
    }
  }
  import LazyIconPicker from '$lib/components/LazyIconPicker.svelte';
  import QuickCaptureWidget from '$lib/components/QuickCaptureWidget.svelte';
  import ScientificCalculator from '$lib/components/ScientificCalculator.svelte';
  import VirtualList from '$lib/components/VirtualList.svelte';
  import {
    notes,
    notesLoading,
    loadNotes,
    loadMore,
    hasMoreNotes,
    loadingMore,
    createNote,
    updateNote,
    deleteNote,
    aiSuggestions,
    selectedNoteIds,
    bulkMode,
    toggleNoteSelection,
    selectAllNotes,
    clearNoteSelection,
    deleteSelectedNotes,
    tagSelectedNotes,
    untagSelectedNotes,
  } from '$lib/stores/notes';
  import {
    buildTree,
    flattenTree,
    extractFrontmatter,
    getFileIcon,
    type SortMode,
    type FlatNode,
  } from '$lib/utils/fileTree';
  import TreeContextMenu from '$lib/components/TreeContextMenu.svelte';
  import FolderPicker from '$lib/components/FolderPicker.svelte';
  import {
    showHiddenFiles,
    showTrash,
    folderMetaStore,
    updateFolderMeta,
  } from '$lib/stores/settings';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { captureSnapshot, getSnapshot } from '$lib/stores/pageSnapshots';
  import { api, type Note } from '$lib/api';
  import { DEFAULT_GOAL_COLOR } from '$lib/utils/goalColors';
  import { t } from 'svelte-i18n';

  // ── State ────────────────────────────────────────────────────────────────────
  let search = '';
  let selectedNote: Note | null = null;
  let showEditor = false;
  let editingNew = false;
  let viewMode: 'tree' | 'list' = 'tree';
  let dailySourcePath: string | null = null;
  let dailyInitialTitle = '';
  let dailyNotesConfigured = false;
  let deleteConfirm = false;
  let totalNotes = 0;

  // Folder customization
  let editingFolder: string | null = null;
  let folderColor = DEFAULT_GOAL_COLOR;
  let folderIcon = 'Folder';

  let editingFolderNote: Note | null = null;
  let creatingFolder = false;

  // ── Context menu ─────────────────────────────────────────────────────────────
  let ctxMenu: { x: number; y: number; node: import('$lib/utils/fileTree').FlatNode } | null = null;
  let renamingNode: import('$lib/utils/fileTree').FlatNode | null = null;
  let renameValue = '';
  let movingNode: import('$lib/utils/fileTree').FlatNode | null = null;

  function handleContextMenu(e: MouseEvent, node: import('$lib/utils/fileTree').FlatNode) {
    e.preventDefault();
    e.stopPropagation();
    ctxMenu = { x: e.clientX, y: e.clientY, node };
  }

  function handleRename() {
    if (!ctxMenu) return;
    renamingNode = ctxMenu.node;
    renameValue = ctxMenu.node.name;
    ctxMenu = null;
  }

  async function confirmRename() {
    if (!renamingNode || !renameValue.trim()) {
      renamingNode = null;
      return;
    }
    const node = renamingNode;
    renamingNode = null;
    if (node.type === 'file' && node.note) {
      await updateNote(node.note.id, { title: renameValue.trim() });
    }
  }

  function handleMove() {
    if (!ctxMenu) return;
    movingNode = ctxMenu.node;
    ctxMenu = null;
  }

  async function confirmMove(targetPath: string) {
    const node = movingNode;
    if (!node || !node.note) {
      movingNode = null;
      return;
    }
    const note = node.note;
    movingNode = null;
    const newPath = targetPath ? `${targetPath}/${node.name}` : node.name;
    await api.notes.update(note.id, { source_path: newPath });
    await loadNotes();
  }

  function handleDeleteNote() {
    if (!ctxMenu || !ctxMenu.node.note) {
      ctxMenu = null;
      return;
    }
    const note = ctxMenu.node.note;
    ctxMenu = null;
    if (confirm(`¿Eliminar "${note.title}"?`)) {
      deleteNote(note.id);
    }
  }

  function handleNewNoteInFolder() {
    if (!ctxMenu) return;
    ctxMenu = null;
    openNew();
  }

  function handleDeleteFolder() {
    if (!ctxMenu) return;
    const menu = ctxMenu;
    const path = menu.node.path;
    ctxMenu = null;
    if (confirm(`¿Eliminar carpeta "${menu.node.name}" y todas sus notas?`)) {
      // Delete notes in this folder
      const ids = $notes
        .filter((n) => n.source_path && n.source_path.includes(path))
        .map((n) => n.id);
      Promise.all(ids.map((id) => deleteNote(id))).then(() => loadNotes());
    }
  }

  let newFolderName = '';
  let newFolderParent = '';
  let newFolderIcon = 'Folder';
  let newFolderColor = DEFAULT_GOAL_COLOR;
  async function openFolderCustomizer(node: {
    path: string;
    color?: string | null;
    icon?: string | null;
    note?: Note;
  }) {
    editingFolder = node.path;
    folderColor = node.color || DEFAULT_GOAL_COLOR;
    folderIcon = node.icon || 'Folder';
    editingFolderNote = node.note || null;
  }

  // ── Explorer toolbar state ───────────────────────────────────────────────────
  let sortMode: SortMode = 'edit-new';
  let showSortMenu = false;
  let allCollapsed = false;
  let notesPrefsReady = false;
  let listScrollEl: HTMLDivElement | null = null;
  let treeScrollTop = 0;
  let listScrollTop = 0;
  let scrollReady = false;
  let virtualScrollTop = 0;
  let lastVirtualScroll = 0;
  let lastRestoredViewMode: 'tree' | 'list' = 'tree';

  const SORT_MODES: SortMode[] = ['az', 'za', 'edit-new', 'edit-old', 'create-new', 'create-old'];
  const RECENT_TITLE_SCROLL_MIN_CHARS = 34;

  function autoScrollTitle(node: HTMLSpanElement, title = '') {
    const textEl = node.querySelector<HTMLSpanElement>('.recent-name-text');
    if (!textEl) return;

    let frameId = 0;
    let resizeObserver: ResizeObserver | null = null;

    const update = () => {
      const safeTitle = (title || textEl.textContent || '').trim();
      const overflowPx = Math.ceil(textEl.scrollWidth - node.clientWidth);
      const shouldScroll = safeTitle.length >= RECENT_TITLE_SCROLL_MIN_CHARS && overflowPx > 6;

      textEl.classList.toggle('is-overflowing', shouldScroll);

      if (shouldScroll) {
        textEl.style.setProperty('--scroll-distance', `${overflowPx}px`);
        const durationSec = Math.min(14, Math.max(6, overflowPx / 22 + 4));
        textEl.style.setProperty('--scroll-duration', `${durationSec}s`);
      } else {
        textEl.style.removeProperty('--scroll-distance');
        textEl.style.removeProperty('--scroll-duration');
      }
    };

    const scheduleUpdate = () => {
      cancelAnimationFrame(frameId);
      frameId = requestAnimationFrame(update);
    };

    scheduleUpdate();

    if (typeof ResizeObserver !== 'undefined') {
      resizeObserver = new ResizeObserver(scheduleUpdate);
      resizeObserver.observe(node);
      resizeObserver.observe(textEl);
    }
    window.addEventListener('resize', scheduleUpdate);

    return {
      update(newTitle = '') {
        title = newTitle;
        scheduleUpdate();
      },
      destroy() {
        cancelAnimationFrame(frameId);
        resizeObserver?.disconnect();
        window.removeEventListener('resize', scheduleUpdate);
      },
    };
  }

  function isSortMode(value: unknown): value is SortMode {
    return typeof value === 'string' && SORT_MODES.includes(value as SortMode);
  }

  function persistNotesPrefs() {
    // When VirtualList is used (>50 items), listScrollEl.scrollTop is always 0.
    // Use virtualScrollTop (bound to VirtualList's internal scroll) instead.
    const itemCount = viewMode === 'tree' ? flatNodes.length : filtered.length;
    const currentScroll = itemCount > 50 ? virtualScrollTop : (listScrollEl?.scrollTop ?? 0);
    const nextTreeScrollTop = viewMode === 'tree' ? currentScroll : treeScrollTop;
    const nextListScrollTop = viewMode === 'list' ? currentScroll : listScrollTop;

    treeScrollTop = nextTreeScrollTop;
    listScrollTop = nextListScrollTop;

    patchUserSettings({
      notesUi: {
        panelWidth,
        sortMode,
        viewMode,
        allCollapsed,
        collapsedPaths: Array.from(collapsed),
        search,
        selectedNoteId: selectedNote?.id ?? null,
        treeScrollTop: nextTreeScrollTop,
        listScrollTop: nextListScrollTop,
      },
    });
  }

  function setSortMode(mode: SortMode) {
    sortMode = mode;
    showSortMenu = false;
    if (notesPrefsReady) persistNotesPrefs();
  }

  function handleCreateFolder() {
    creatingFolder = true;
    newFolderName = '';
    newFolderParent = '';
    newFolderIcon = 'Folder';
    newFolderColor = DEFAULT_GOAL_COLOR;
  }

  function toggleCollapseAll() {
    allCollapsed = !allCollapsed;
    if (allCollapsed) {
      const folders = flatNodes.filter((n) => n.type === 'folder');
      for (const f of folders) collapsed.add(f.path);
    } else {
      collapsed.clear();
    }
    collapsed = collapsed;
    if (notesPrefsReady) persistNotesPrefs();
  }

  function getNoteVisual(note: Note) {
    const fm = extractFrontmatter(note.content || '');
    return {
      icon: fm.icon || getFileIcon(note.title, note.content || ''),
      color: fm.color || undefined,
      pack: fm.pack || undefined,
    };
  }

  // Resizable panel — min width matches the dashboard's default panel width
  // so the left sidebar (plant, timer, etc.) on the index page is never
  // crushed below its intended size. Moving right is unrestricted up to MAX_W.
  const MIN_W = 260;
  const MAX_W = 520;
  let panelWidth = 260;
  let dragging = false;

  // Tree collapse state — Set of collapsed folder paths
  let collapsed = new Set<string>();
  $: collapsedSignature = Array.from(collapsed).sort().join('|');

  $: showNew = $page.url.searchParams.get('new') === '1';
  $: selectedId = $page.url.searchParams.get('id');
  $: urlSearch = $page.url.searchParams.get('search');

  // Handle URL changes reactively
  $: if (urlSearch !== null) {
    search = urlSearch;
  }

  $: if (showNew && notesPrefsReady) {
    const urlTitle = $page.url.searchParams.get('title');
    if (!editingNew || dailyInitialTitle !== (urlTitle ?? '')) {
      openNew();
      if (urlTitle) {
        dailyInitialTitle = urlTitle;
      }
    }
  }

  $: if (selectedId && $notes.length > 0) {
    const n = $notes.find((n) => String(n.id) === selectedId);
    if (n && selectedNote?.id !== n.id) {
      openNote(n);
    }
  } else if (!selectedId && showEditor && !editingNew) {
    // If we were viewing a note and ID cleared, close editor
    showEditor = false;
    selectedNote = null;
  }

  // Flat filtered list for list mode
  $: filtered = $notes.filter(
    (n) =>
      !search ||
      n.title.toLowerCase().includes(search.toLowerCase()) ||
      n.tags.some((t) => t.includes(search.toLowerCase()))
  );

  $: editorNote = editingNew
    ? isMomentary
      ? ({ ...momentaryDraft, id: -1, source: 'momentary' } as Note)
      : null
    : selectedNote;

  // Tree → flat list (no recursive component, avoids Svelte 5 HMR issues)
  $: tree = buildTree(
    $notes,
    viewMode === 'tree' ? search : '',
    $showTrash,
    $showHiddenFiles,
    sortMode,
    $folderMetaStore
  );
  $: flatNodes = flattenTree(tree, collapsed);
  let historyStack: number[] = [];
  let historyIndex = -1;
  let isNavigatingHistory = false;

  async function addToHistory(id: number) {
    if (isNavigatingHistory) return;

    // Check if we are just moving to an adjacent item (e.g. browser back/forward)
    if (historyIndex > 0 && historyStack[historyIndex - 1] === id) {
      historyIndex--;
      return;
    }
    if (
      historyIndex >= 0 &&
      historyIndex < historyStack.length - 1 &&
      historyStack[historyIndex + 1] === id
    ) {
      historyIndex++;
      return;
    }

    // If it's the same as current, do nothing
    if (historyIndex >= 0 && historyStack[historyIndex] === id) return;

    // New branch: clear forward history and push
    const newStack = historyStack.slice(0, historyIndex + 1);
    historyStack = [...newStack, id].slice(-50);
    historyIndex = historyStack.length - 1;
  }

  $: hasPrev = historyIndex > 0;
  $: hasNext = historyIndex < historyStack.length - 1;

  async function goToPrev() {
    if (hasPrev) {
      isNavigatingHistory = true;
      historyIndex--;
      const id = historyStack[historyIndex];
      const n = $notes.find((n) => n.id === id);
      if (n) openNote(n);
      await tick();
      isNavigatingHistory = false;
    }
  }

  async function goToNext() {
    if (hasNext) {
      isNavigatingHistory = true;
      historyIndex++;
      const id = historyStack[historyIndex];
      const n = $notes.find((n) => n.id === id);
      if (n) openNote(n);
      await tick();
      isNavigatingHistory = false;
    }
  }

  $: if (notesPrefsReady) {
    viewMode;
    sortMode;
    panelWidth;
    allCollapsed;
    collapsedSignature;
    search;
    selectedNote?.id;
    persistNotesPrefs();
  }

  $: if (notesPrefsReady && viewMode !== lastRestoredViewMode) {
    lastRestoredViewMode = viewMode;
    const target = viewMode === 'tree' ? treeScrollTop : listScrollTop;
    lastVirtualScroll = target;
    virtualScrollTop = target;
    tick().then(() => {
      if (!listScrollEl) return;
      listScrollEl.scrollTop = target;
      lastVirtualScroll = target;
      virtualScrollTop = target;
    });
  }

  onMount(async () => {
    // Load prefs from localStorage FIRST (synchronous) — before any async
    // operation so we know the target scroll position ASAP.
    const saved = loadUserSettings().notesUi;
    if (saved?.panelWidth !== undefined) {
      panelWidth = Math.max(MIN_W, Math.min(MAX_W, Number(saved.panelWidth)));
    }
    if (isSortMode(saved?.sortMode)) {
      sortMode = saved.sortMode;
    }
    if (saved?.viewMode === 'tree' || saved?.viewMode === 'list') {
      viewMode = saved.viewMode;
      lastRestoredViewMode = saved.viewMode;
    }
    if (typeof saved?.search === 'string') {
      search = saved.search;
    }
    if (Array.isArray(saved?.collapsedPaths)) {
      collapsed = new Set(saved.collapsedPaths.filter((p) => typeof p === 'string'));
    }
    allCollapsed = Boolean(saved?.allCollapsed);
    treeScrollTop = Number.isFinite(Number(saved?.treeScrollTop))
      ? Number(saved?.treeScrollTop)
      : 0;
    listScrollTop = Number.isFinite(Number(saved?.listScrollTop))
      ? Number(saved?.listScrollTop)
      : 0;

    const snap = getSnapshot('/notes');
    if (snap) {
      search = snap.state.search ?? '';
      viewMode = snap.state.viewMode ?? 'tree';
      sortMode = snap.state.sortMode ?? 'edit-new';
      allCollapsed = snap.state.allCollapsed ?? false;
      if (snap.state.collapsedPaths) collapsed = new Set(snap.state.collapsedPaths);
      if (snap.state.selectedNoteId) selectedId = snap.state.selectedNoteId;
    }

    notesPrefsReady = true;

    // Kick off note loading (loads from cache synchronously inside loadNotes,
    // then fetches from API asynchronously).
    loadNotes();

    // Wait one tick for Svelte to render the cached notes into the DOM.
    await tick();

    // Apply scroll position BEFORE making the list visible.
    const target = viewMode === 'tree' ? treeScrollTop : listScrollTop;
    const itemCount = viewMode === 'tree' ? flatNodes.length : filtered.length;
    if (itemCount > 50) {
      lastVirtualScroll = target;
      virtualScrollTop = target;
    } else if (listScrollEl) {
      listScrollEl.scrollTop = target;
    }

    // Now reveal the list — the user never sees it at position 0.
    scrollReady = true;

    // Fire async config/stats fetches in parallel (non-blocking).
    api.config
      .get()
      .then((config) => {
        dailyNotesConfigured = Boolean(
          config.obsidian_vault_path?.trim() && config.daily_notes_folder?.trim()
        );
      })
      .catch(() => {
        dailyNotesConfigured = false;
      });

    api.stats
      .system()
      .then((stats) => {
        totalNotes = stats.notes;
      })
      .catch(() => {
        totalNotes = 0;
      });

    requestAnimationFrame(async () => {
      await tick();
      if (showNew) openNew();
      if (selectedId) {
        const n = $notes.find((n) => String(n.id) === selectedId);
        if (n) openNote(n);
      } else if (typeof saved?.selectedNoteId === 'number') {
        const n = $notes.find((note) => note.id === saved.selectedNoteId);
        if (n) openNote(n);
      }
    });

    window.addEventListener('beforeunload', handleBeforeUnload);
  });

  onDestroy(() => window.removeEventListener('beforeunload', handleBeforeUnload));

  function handleBeforeUnload() {
    // Scroll position is persisted via onListScroll/onVirtualScrollChange
    // → persistNotesPrefs → localStorage. No need to capture it in the
    // snapshot (which is stale in SPA navigation anyway).
    captureSnapshot(
      '/notes',
      {
        search,
        viewMode,
        sortMode,
        allCollapsed,
        collapsedPaths: Array.from(collapsed),
        selectedNoteId: selectedNote?.id,
      },
      []
    );
  }

  // ── Resize ───────────────────────────────────────────────────────────────────
  function startResize(e: MouseEvent) {
    e.preventDefault();
    dragging = true;
    const startX = e.clientX;
    const startW = panelWidth;
    function onMove(e: MouseEvent) {
      panelWidth = Math.max(MIN_W, Math.min(MAX_W, startW + (e.clientX - startX)));
    }
    function onUp() {
      dragging = false;
      if (notesPrefsReady) persistNotesPrefs();
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }

  // ── Tree toggle ──────────────────────────────────────────────────────────────
  function toggleFolder(path: string) {
    if (collapsed.has(path)) collapsed.delete(path);
    else collapsed.add(path);
    collapsed = collapsed; // trigger reactivity
    if (notesPrefsReady) persistNotesPrefs();
  }

  function onListScroll() {
    if (!notesPrefsReady || !listScrollEl) return;
    // When VirtualList is used (>50 items), the outer .list-scroll container
    // doesn't scroll — VirtualList has its own internal scroll container.
    // Scroll position is tracked via onVirtualScrollChange callback instead.
    const itemCount = viewMode === 'tree' ? flatNodes.length : filtered.length;
    if (itemCount > 50) return;
    if (viewMode === 'tree') treeScrollTop = listScrollEl.scrollTop;
    else listScrollTop = listScrollEl.scrollTop;
    persistNotesPrefs();
  }

  // Called by VirtualList when its internal scroll position changes.
  // Replaces a reactive block that caused a cyclical dependency.
  function onVirtualScrollChange(scrollVal: number) {
    if (!notesPrefsReady) return;
    lastVirtualScroll = scrollVal;
    if (viewMode === 'tree') treeScrollTop = scrollVal;
    else listScrollTop = scrollVal;
    persistNotesPrefs();
  }

  // ── Note actions ─────────────────────────────────────────────────────────────
  function openNote(note: Note) {
    if (selectedId !== String(note.id)) {
      goto(`/notes?id=${note.id}`, { keepFocus: true, noScroll: true });
    }
    selectedNote = note;
    addToHistory(note.id);
    showEditor = true;
    editingNew = false;
    aiSuggestions.set([]);
    ensureNoteEditor();
  }

  function openNew() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = false;
    dailySourcePath = null;
    dailyInitialTitle = '';
    aiSuggestions.set([]);
    ensureNoteEditor();
  }

  function openMomentary() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = true;
    dailySourcePath = null;
    dailyInitialTitle = '';
    ensureNoteEditor();
  }

  function normalizeVaultFolder(path: string): string {
    return path.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
  }

  function buildDailySourcePath(vaultPath: string, folder: string, fileName: string): string {
    const cleanVault = vaultPath.replace(/[\\/]+$/, '');
    const cleanFolder = normalizeVaultFolder(folder);
    return `${cleanVault}/${cleanFolder}/${fileName}`;
  }

  function openSettingsForDaily() {
    window.dispatchEvent(new CustomEvent('joidy:open-settings'));
  }

  async function openDaily() {
    if (!dailyNotesConfigured) {
      openSettingsForDaily();
      return;
    }

    const config = await api.config.get();

    const vaultPath = (config.obsidian_vault_path || '').trim();
    const dailyFolder = (config.daily_notes_folder || '').trim();

    if (!vaultPath || !dailyFolder) return;

    const today = new Date().toISOString().split('T')[0];
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = false; // Usually daily notes are real
    dailyInitialTitle = today;
    dailySourcePath = buildDailySourcePath(vaultPath, dailyFolder, `${today}.md`);
    aiSuggestions.set([]);
    ensureNoteEditor();
  }

  function closeEditor() {
    showEditor = false;
    selectedNote = null;
    dailySourcePath = null;
    dailyInitialTitle = '';
    goto('/notes');
  }

  async function handleSave(e: CustomEvent<{ title: string; content: string; tags: string[] }>) {
    const { title, content, tags } = e.detail;
    if (isMomentary) {
      momentaryDraft = { title, content, tags };
      return;
    }
    if (editingNew) {
      if (dailyInitialTitle && !dailySourcePath) return;
      const n = await createNote(title, content, tags, dailySourcePath);
      if (n) {
        selectedNote = n;
        editingNew = false;
      }
    } else if (selectedNote) {
      await updateNote(selectedNote.id, { title, content, tags });
    }
  }

  async function handleDelete() {
    if (!deleteConfirm) {
      deleteConfirm = true;
      return;
    }
    if (selectedNote) {
      await deleteNote(selectedNote.id);
      deleteConfirm = false;
      closeEditor();
    }
  }

  // ── Dashboard Empty State ──
  let isMomentary = false;
  let momentaryDraft = { title: 'Borrador Efímero', content: '', tags: [] as string[] };

  function quickNoteFromScratch() {
    openNew();
    // We can't easily pre-fill NoteEditor here without more store logic,
    // but the user just wants the "normal" creation flow to be the priority.
  }
</script>

<svelte:window
  onclick={() => {
    if (showSortMenu) showSortMenu = false;
  }}
  onkeydown={(e) => e.key === 'Escape' && (deleteConfirm = false)}
/>

<div class="notes-page" class:dragging style="--panel-w: {panelWidth}px">
  <!-- ── List / Tree panel ─────────────────────────────────────────────────── -->
  <aside class="notes-list">
    <div class="tree-actions-bar">
      <div class="actions-left">
        <button
          class="icon-btn"
          title={$t('notesPage.createNote')}
          aria-label={$t('notesPage.createNote')}
          onclick={openNew}><FilePen size={13} /></button
        >
        <button
          class="icon-btn"
          title={$t('notesPage.createFolder')}
          aria-label={$t('notesPage.createFolder')}
          onclick={handleCreateFolder}><FolderPlus size={13} /></button
        >
        <div class="sort-wrapper">
          <button
            class="icon-btn"
            title={$t('notesPage.changeOrder')}
            aria-label={$t('notesPage.changeOrder')}
            onclick={(e) => {
              e.stopPropagation();
              showSortMenu = !showSortMenu;
            }}
          >
            <ArrowUpDown size={13} />
          </button>
          {#if showSortMenu}
            <div class="sort-menu" onclick={(e) => e.stopPropagation()}>
              <button
                class="sort-btn"
                class:active={sortMode === 'az'}
                onclick={() => setSortMode('az')}>{$t('notesPage.sortAz')}</button
              >
              <button
                class="sort-btn"
                class:active={sortMode === 'za'}
                onclick={() => setSortMode('za')}>{$t('notesPage.sortZa')}</button
              >
              <div class="sort-divider"></div>
              <button
                class="sort-btn"
                class:active={sortMode === 'edit-new'}
                onclick={() => setSortMode('edit-new')}
                >{$t('notesPage.sortEditNew')}
                {#if sortMode === 'edit-new'}✓{/if}</button
              >
              <button
                class="sort-btn"
                class:active={sortMode === 'edit-old'}
                onclick={() => setSortMode('edit-old')}
                >{$t('notesPage.sortEditOld')}
                {#if sortMode === 'edit-old'}✓{/if}</button
              >
              <div class="sort-divider"></div>
              <button
                class="sort-btn"
                class:active={sortMode === 'create-new'}
                onclick={() => setSortMode('create-new')}
                >{$t('notesPage.sortCreateNew')}
                {#if sortMode === 'create-new'}✓{/if}</button
              >
              <button
                class="sort-btn"
                class:active={sortMode === 'create-old'}
                onclick={() => setSortMode('create-old')}
                >{$t('notesPage.sortCreateOld')}
                {#if sortMode === 'create-old'}✓{/if}</button
              >
            </div>
          {/if}
        </div>
        <button
          class="icon-btn"
          title={allCollapsed ? 'Expandir todo' : 'Comprimir todo'}
          aria-label={allCollapsed ? 'Expandir todo' : 'Comprimir todo'}
          onclick={toggleCollapseAll}
        >
          <ChevronsUpDown size={13} />
        </button>
      </div>

      <div class="actions-right">
        <button
          class="icon-btn"
          class:active={viewMode === 'tree'}
          title="Vista de carpetas"
          aria-label="Vista de carpetas"
          onclick={() => {
            viewMode = 'tree';
            if (notesPrefsReady) persistNotesPrefs();
          }}
        >
          <FolderTree size={13} />
        </button>
        <button
          class="icon-btn"
          class:active={viewMode === 'list'}
          title="Vista de lista"
          aria-label="Vista de lista"
          onclick={() => {
            viewMode = 'list';
            if (notesPrefsReady) persistNotesPrefs();
          }}
        >
          <List size={13} />
        </button>
      </div>
    </div>

    <div class="list-toolbar">
      <div class="search-wrap">
        <Search size={11} style="color: var(--text-muted); flex-shrink:0;" />
        <input class="search-input" bind:value={search} placeholder={$t('notesPage.search')} />
        {#if search}
          <button
            class="icon-btn"
            onclick={() => (search = '')}
            title={$t('notesPage.clear')}
            aria-label={$t('notesPage.clear')}
          >
            <X size={10} />
          </button>
        {/if}
      </div>
      <button
        class="toolbar-btn bulk-toggle"
        class:active={$bulkMode}
        aria-label={$t('notesPage.bulkMode')}
        onclick={() => {
          bulkMode.set(!$bulkMode);
          clearNoteSelection();
        }}
      >
        <SquareCheckBig size={14} />
      </button>
    </div>

    <div class="list-meta">
      <span
        >{$bulkMode
          ? `${$selectedNoteIds.size} seleccionadas`
          : `${totalNotes || $notes.length} notas`}</span
      >
      {#if search}<span class="sep">·</span><span>{filtered.length} resultados</span>{/if}
      {#if $bulkMode}
        <button
          class="toolbar-btn select-all"
          onclick={$selectedNoteIds.size === filtered.length ? clearNoteSelection : selectAllNotes}
        >
          {$selectedNoteIds.size === filtered.length ? 'Deseleccionar todo' : 'Seleccionar todo'}
        </button>
      {/if}
    </div>

    {#if $bulkMode && $selectedNoteIds.size > 0}
      <div class="bulk-actions">
        <span class="bulk-count"
          >{$selectedNoteIds.size} nota{#if $selectedNoteIds.size !== 1}s{/if}</span
        >
        <button
          class="bulk-btn danger"
          onclick={() => {
            if (confirm(`¿Eliminar ${$selectedNoteIds.size} nota(s)?`)) deleteSelectedNotes();
          }}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><polyline points="3 6 5 6 21 6" /><path
              d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
            /></svg
          >
          Eliminar
        </button>
        <button
          class="bulk-btn"
          onclick={() => {
            const t = prompt('Tags a añadir (separadas por coma):');
            if (t)
              tagSelectedNotes(
                t
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
              );
          }}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path
              d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"
            /><line x1="7" y1="7" x2="7.01" y2="7" /></svg
          >
          Etiquetar
        </button>
        <button
          class="bulk-btn"
          onclick={() => {
            const t = prompt('Tags a quitar (separadas por coma):');
            if (t)
              untagSelectedNotes(
                t
                  .split(',')
                  .map((s) => s.trim())
                  .filter(Boolean)
              );
          }}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            ><path
              d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"
            /><line x1="7" y1="7" x2="7.01" y2="7" /><line x1="15" y1="9" x2="9" y2="15" /></svg
          >
          Desetiquetar
        </button>
        <button class="bulk-btn" onclick={() => clearNoteSelection()}> Cancelar </button>
      </div>
    {/if}

    <div
      class="list-scroll"
      class:scroll-ready={scrollReady}
      bind:this={listScrollEl}
      onscroll={onListScroll}
    >
      {#if $notesLoading}
        <div class="empty-msg">{$t('notesPage.loading')}</div>
      {:else if viewMode === 'tree'}
        {#if flatNodes.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else if flatNodes.length > 50}
          <VirtualList
            items={flatNodes}
            itemHeight={26}
            getKey={(n, i) => n.path ?? i}
            bind:scrollTop={virtualScrollTop}
            onScrollChange={onVirtualScrollChange}
            let:item
            let:index
          >
            {#if item.type === 'folder'}
              <div
                class="tree-row folder-row"
                style="padding-left: {8 + item.depth * 14}px"
                role="button"
                tabindex="0"
                aria-expanded={!collapsed.has(item.path)}
                onclick={() => toggleFolder(item.path)}
                onkeydown={(e) =>
                  (e.key === 'Enter' || e.key === ' ') &&
                  (e.preventDefault(), toggleFolder(item.path))}
                oncontextmenu={(e) => handleContextMenu(e, item)}
              >
                <span class="chevron" class:open={!collapsed.has(item.path)}>
                  <ChevronRight size={11} />
                </span>
                <div class="t-icon">
                  <DynamicIcon name={item.icon} size={13} color={item.color} pack={item.pack} />
                </div>
                <span class="t-name folder-name">{item.name}</span>
                <button
                  class="folder-settings-btn"
                  title={$t('notesPage.customizeFolder')}
                  aria-label={$t('notesPage.customizeFolder')}
                  onclick={(e) => {
                    e.stopPropagation();
                    openFolderCustomizer(item);
                  }}
                >
                  <Settings size={10} />
                </button>
                <span class="t-count">{item.childCount}</span>
              </div>
            {:else}
              <div
                class="tree-row file-row"
                class:active={item.note?.id === selectedNote?.id}
                style="padding-left: {20 + item.depth * 14}px"
                role="button"
                tabindex="0"
                aria-selected={item.note?.id === selectedNote?.id}
                onclick={() => item.note && openNote(item.note)}
                onkeydown={(e) =>
                  (e.key === 'Enter' || e.key === ' ') &&
                  item.note &&
                  (e.preventDefault(), openNote(item.note))}
                oncontextmenu={(e) => handleContextMenu(e, item)}
              >
                <div class="t-icon file-icon">
                  <DynamicIcon name={item.icon} size={11} color={item.color} pack={item.pack} />
                </div>
                <span class="t-name file-name">{item.name}</span>
                <button
                  class="folder-settings-btn"
                  title={$t('notesPage.customizeNote')}
                  aria-label={$t('notesPage.customizeNote')}
                  onclick={(e) => {
                    e.stopPropagation();
                    openFolderCustomizer({
                      path: item.note?.source_path || item.path,
                      icon: item.icon,
                      color: item.color,
                      note: item.note,
                    });
                  }}
                >
                  <Settings size={10} />
                </button>
              </div>
            {/if}
          </VirtualList>
        {:else}
          <div class="tree-wrap">
            {#each flatNodes as node (node.path)}
              {#if node.type === 'folder'}
                <div
                  class="tree-row folder-row"
                  style="padding-left: {8 + node.depth * 14}px"
                  role="button"
                  tabindex="0"
                  aria-expanded={!collapsed.has(node.path)}
                  onclick={() => toggleFolder(node.path)}
                  onkeydown={(e) =>
                    (e.key === 'Enter' || e.key === ' ') &&
                    (e.preventDefault(), toggleFolder(node.path))}
                  oncontextmenu={(e) => handleContextMenu(e, node)}
                >
                  <span class="chevron" class:open={!collapsed.has(node.path)}>
                    <ChevronRight size={11} />
                  </span>
                  <div class="t-icon">
                    <DynamicIcon name={node.icon} size={13} color={node.color} pack={node.pack} />
                  </div>
                  <span class="t-name folder-name">{node.name}</span>
                  <button
                    class="folder-settings-btn"
                    title={$t('notesPage.customizeFolder')}
                    aria-label={$t('notesPage.customizeFolder')}
                    onclick={(e) => {
                      e.stopPropagation();
                      openFolderCustomizer(node);
                    }}
                  >
                    <Settings size={10} />
                  </button>
                  <span class="t-count">{node.childCount}</span>
                </div>
              {:else}
                <div
                  class="tree-row file-row"
                  class:active={node.note?.id === selectedNote?.id}
                  style="padding-left: {20 + node.depth * 14}px"
                  role="button"
                  tabindex="0"
                  aria-selected={node.note?.id === selectedNote?.id}
                  onclick={() => node.note && openNote(node.note)}
                  onkeydown={(e) =>
                    (e.key === 'Enter' || e.key === ' ') &&
                    node.note &&
                    (e.preventDefault(), openNote(node.note))}
                  oncontextmenu={(e) => handleContextMenu(e, node)}
                >
                  <div class="t-icon file-icon">
                    <DynamicIcon name={node.icon} size={11} color={node.color} pack={node.pack} />
                  </div>
                  <span class="t-name file-name">{node.name}</span>
                  <button
                    class="folder-settings-btn"
                    title={$t('notesPage.customizeNote')}
                    aria-label={$t('notesPage.customizeNote')}
                    onclick={(e) => {
                      e.stopPropagation();
                      openFolderCustomizer({
                        path: node.note?.source_path || node.path,
                        icon: node.icon,
                        color: node.color,
                        note: node.note,
                      });
                    }}
                  >
                    <Settings size={10} />
                  </button>
                </div>
              {/if}
            {/each}
          </div>
        {/if}
      {:else}
        {#if filtered.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else if filtered.length > 50}
          <VirtualList
            items={filtered}
            itemHeight={52}
            bind:scrollTop={virtualScrollTop}
            onScrollChange={onVirtualScrollChange}
            let:item
            let:index
          >
            <NoteCard
              note={item}
              active={selectedNote?.id === item.id}
              selected={$selectedNoteIds.has(item.id)}
              bulkMode={$bulkMode}
              on:select={(e) => openNote(e.detail)}
              on:toggleSelect={(e) => toggleNoteSelection(e.detail)}
              on:customize={(e) => openFolderCustomizer(e.detail)}
            />
          </VirtualList>
        {:else}
          {#each filtered as note}
            <NoteCard
              {note}
              active={selectedNote?.id === note.id}
              selected={$selectedNoteIds.has(note.id)}
              bulkMode={$bulkMode}
              on:select={(e) => openNote(e.detail)}
              on:toggleSelect={(e) => toggleNoteSelection(e.detail)}
              on:customize={(e) => openFolderCustomizer(e.detail)}
            />
          {/each}
        {/if}
      {/if}

      {#if !$notesLoading && $hasMoreNotes && !search}
        <button class="load-more-btn" onclick={() => loadMore()} disabled={$loadingMore}>
          {$loadingMore ? $t('notesPage.loading') : $t('notesPage.loadMore')}
        </button>
      {/if}
    </div>
  </aside>

  <!-- Folder customize modal -->
  <!-- Create folder modal -->
  {#if creatingFolder}
    <div class="folder-modal-backdrop" onclick={() => (creatingFolder = false)}>
      <div class="folder-modal" onclick={(e) => e.stopPropagation()}>
        <h3 class="folder-modal-title">{$t('notesPage.createFolderTitle')}</h3>

        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
          <span class="folder-label mono">{$t('notesPage.name')}</span>
          <input
            type="text"
            class="input mono"
            bind:value={newFolderName}
            placeholder={$t('notesPage.newFolderPlaceholder')}
            style="width:100%; box-sizing:border-box;"
          />
        </div>

        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
          <span class="folder-label mono">{$t('notesPage.location')}</span>
          <select
            class="input mono"
            bind:value={newFolderParent}
            style="width:100%; box-sizing:border-box;"
          >
            <option value="">(Raíz)</option>
            {#each flatNodes.filter((n) => n.type === 'folder') as f}
              <option value={f.path}>{f.path}</option>
            {/each}
          </select>
        </div>

        <div class="folder-color-row">
          <span class="folder-label mono">{$t('notesPage.color')}</span>
          <input type="color" class="folder-color-input" bind:value={newFolderColor} />
          <input
            type="text"
            class="folder-hex-input mono"
            maxlength="7"
            bind:value={newFolderColor}
          />
        </div>

        <div class="folder-icon-row">
          <span class="folder-label mono">{$t('notesPage.icon')}</span>
          <LazyIconPicker
            selected={newFolderIcon}
            color={newFolderColor}
            onSelect={(ic) => (newFolderIcon = ic)}
          />
        </div>

        <div class="folder-modal-btns">
          <button onclick={() => (creatingFolder = false)}>{$t('notesPage.cancel')}</button>
          <button
            class="primary"
            disabled={!newFolderName.trim()}
            onclick={async () => {
              if (!newFolderName.trim()) return;
              const targetPath = newFolderParent
                ? `${newFolderParent}/${newFolderName.trim()}`
                : newFolderName.trim();
              try {
                await api.folders.create(targetPath);
                updateFolderMeta(targetPath, { icon: newFolderIcon, color: newFolderColor });
                creatingFolder = false;
                // Refresh tree
                const ns = await api.notes.list();
                notes.set(ns);
              } catch (e) {
                alert((e as any).message || 'Error al crear carpeta');
              }
            }}>{$t('notesPage.create')}</button
          >
        </div>
      </div>
    </div>
  {/if}

  {#key ctxMenu}
    {#if ctxMenu}
      <TreeContextMenu
        x={ctxMenu.x}
        y={ctxMenu.y}
        node={ctxMenu.node}
        on:close={() => (ctxMenu = null)}
        on:rename={handleRename}
        on:move={handleMove}
        on:deleteNote={handleDeleteNote}
        on:newNoteInFolder={handleNewNoteInFolder}
        on:deleteFolder={handleDeleteFolder}
      />
    {/if}
  {/key}

  {#if renamingNode}
    <div class="folder-modal-backdrop" onclick={() => (renamingNode = null)}>
      <div class="folder-modal" onclick={(e) => e.stopPropagation()}>
        <h3 class="folder-modal-title">{$t('notesPage.renameTitle')}</h3>
        <input
          type="text"
          class="input mono"
          bind:value={renameValue}
          style="width:100%; box-sizing:border-box; margin-bottom:12px;"
          onkeydown={(e) => e.key === 'Enter' && confirmRename()}
        />
        <div class="folder-modal-btns">
          <button onclick={() => (renamingNode = null)}>{$t('notesPage.cancel')}</button>
          <button class="primary" disabled={!renameValue.trim()} onclick={confirmRename}
            >{$t('notesPage.save')}</button
          >
        </div>
      </div>
    </div>
  {/if}

  {#if movingNode}
    <FolderPicker
      {flatNodes}
      on:close={() => (movingNode = null)}
      on:select={(e) => confirmMove(e.detail)}
    />
  {/if}

  {#if editingFolder}
    <div class="folder-modal-backdrop" onclick={() => (editingFolder = null)}>
      <div class="folder-modal" onclick={(e) => e.stopPropagation()}>
        <h3 class="folder-modal-title">{$t('notesPage.customizeFolderTitle')}</h3>

        <!-- Color bar -->
        <div class="folder-color-row">
          <span class="folder-label mono">{$t('notesPage.color')}</span>
          <input type="color" class="folder-color-input" bind:value={folderColor} />
          <input type="text" class="folder-hex-input mono" maxlength="7" bind:value={folderColor} />
        </div>

        <!-- Icon picker -->
        <div class="folder-icon-row">
          <span class="folder-label mono">{$t('notesPage.icon')}</span>
          <LazyIconPicker
            selected={folderIcon}
            color={folderColor}
            onSelect={(ic) => (folderIcon = ic)}
          />
        </div>

        <div class="folder-modal-btns">
          <button onclick={() => (editingFolder = null)}>{$t('notesPage.cancel')}</button>
          <button
            onclick={async () => {
              if (editingFolder) {
                updateFolderMeta(editingFolder, { icon: folderIcon, color: folderColor });
                if (editingFolderNote) {
                  let content = editingFolderNote.content;
                  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
                  if (match) {
                    let yaml = match[1];
                    if (yaml.match(/(?:^|\n)icon:\s*([^\n]*)/)) {
                      yaml = yaml.replace(/((?:^|\n)icon:\s*)([^\n]*)/, `$1${folderIcon}`);
                    } else {
                      yaml += `\nicon: ${folderIcon}`;
                    }
                    if (yaml.match(/(?:^|\n)iconColor:\s*([^\n]*)/)) {
                      yaml = yaml.replace(/((?:^|\n)iconColor:\s*)([^\n]*)/, `$1${folderColor}`);
                    } else {
                      yaml += `\niconColor: ${folderColor}`;
                    }
                    content = content.replace(/^---\r?\n([\s\S]*?)\r?\n---/, `---\n${yaml}\n---`);
                  } else {
                    content = `---\nicon: ${folderIcon}\niconColor: ${folderColor}\n---\n\n${content}`;
                  }
                  await updateNote(editingFolderNote.id, { content });
                }
              }
              editingFolder = null;
              editingFolderNote = null;
            }}>{$t('notesPage.save')}</button
          >
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <div
    class="resize-handle"
    role="separator"
    aria-orientation="vertical"
    aria-label="Resize panel"
    onmousedown={startResize}
  ></div>

  <!-- ── Editor panel ──────────────────────────────────────────────────────── -->
  <div class="editor-panel">
    {#if deleteConfirm}
      <div class="delete-confirm-bar">
        <span class="delete-confirm-text">¿Eliminar esta nota?</span>
        <span class="delete-confirm-hint">{$t('notesPage.deleteHint')}</span>
        <div class="delete-confirm-actions">
          <button class="btn-cancel" onclick={() => (deleteConfirm = false)}
            >{$t('notesPage.cancel')}</button
          >
          <button class="btn-danger" onclick={handleDelete}>{$t('notesPage.delete')}</button>
        </div>
      </div>
    {/if}
    {#if showEditor}
      {#key editingNew ? (isMomentary ? 'momentary' : 'new') : selectedNote?.id}
        {#if NoteEditor}
          <svelte:component
            this={NoteEditor}
            note={editorNote}
            momentary={isMomentary}
            initialTitle={dailyInitialTitle}
            {hasPrev}
            {hasNext}
            on:save={handleSave}
            on:cancel={closeEditor}
            on:delete={handleDelete}
            on:prev={goToPrev}
            on:next={goToNext}
          />
        {:else}
          <div class="editor-loading caption">{$t('notesPage.editorLoading')}</div>
        {/if}
      {/key}
    {:else}
      <div class="empty-dashboard">
        <DynamicIcon name="Box" size={48} color="var(--border)" />

        <div class="dash-search-container">
          <div class="dash-search">
            <Search size={14} color="var(--text-muted)" />
            <input
              type="text"
              placeholder={$t('notesPage.searchNotePlaceholder')}
              bind:value={search}
            />
          </div>
        </div>

        <div class="dash-quick-capture">
          <QuickCaptureWidget />
        </div>

        <div class="dash-widgets">
          <!-- Quick Note Area -->
          <div class="dash-widget quick-note-widget">
            <div class="dash-widget-title">
              <DynamicIcon name="PenTool" size={13} /> Acciones Rápidas
            </div>
            <div class="dash-action-buttons">
              <button class="dash-btn primary-dash-btn" onclick={openNew}>
                <FilePen size={16} /> Crear nota nueva
              </button>
              <button
                class={`dash-btn secondary-dash-btn daily-note-btn ${dailyNotesConfigured ? '' : 'daily-note-muted'}`}
                onclick={openDaily}
              >
                <span class="daily-note-main">
                  <DynamicIcon name="Calendar" size={16} /> Nota Diaria
                </span>
                <span class="daily-note-hint">{$t('notesPage.configureDailyNote')}</span>
              </button>
              <button class="dash-btn secondary-dash-btn momentary-btn" onclick={openMomentary}>
                <Plus size={16} /> Nota Momentánea
              </button>
            </div>

            <div class="dash-divider"></div>
            <div class="dash-widget-title"><DynamicIcon name="History" size={13} /> Recientes</div>
            <div class="recent-list">
              {#each $notes.slice(0, 3) as note}
                {@const vis = getNoteVisual(note)}
                <button class="recent-item" onclick={() => openNote(note)}>
                  <DynamicIcon
                    name={vis.icon}
                    size={12}
                    color={vis.color || 'var(--text-disabled)'}
                    pack={vis.pack}
                  />
                  <span class="recent-name" use:autoScrollTitle={note.title}>
                    <span class="recent-name-text">{note.title}</span>
                  </span>
                  <span class="recent-time">{new Date(note.updated_at).toLocaleDateString()}</span>
                </button>
              {/each}
            </div>
          </div>

          <div class="dash-widget">
            <div class="dash-widget-title" style="margin-bottom: 5px;">
              <DynamicIcon name="Calculator" size={13} /> Calculadora
            </div>
            <ScientificCalculator />
          </div>
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .notes-page {
    display: grid;
    grid-template-columns: var(--panel-w) 5px 1fr;
    height: 100%;
    overflow: hidden;
  }
  .notes-page.dragging {
    user-select: none;
  }
  .notes-page.dragging * {
    cursor: col-resize;
  }

  /* ── Panel ── */
  .notes-list {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    min-width: 0;
  }

  .tree-actions-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }

  .actions-left {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .actions-right {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .sort-wrapper {
    position: relative;
    display: inline-block;
  }

  .sort-menu {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 4px;
    width: 220px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    z-index: var(--z-dropdown);
  }

  .sort-btn {
    background: transparent;
    border: none;
    text-align: left;
    padding: 6px 12px;
    font-size: 11px;
    color: var(--text-secondary);
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sort-btn:hover {
    background: var(--hover);
    color: var(--text-primary);
  }
  .sort-btn.active {
    color: var(--accent);
    font-weight: 500;
  }

  .sort-divider {
    height: 1px;
    background: var(--border-light);
    margin: 4px 0;
  }

  .list-toolbar {
    display: flex;
    align-items: center;
    gap: 5px;
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
    flex-shrink: 0;
  }

  .search-wrap {
    display: flex;
    align-items: center;
    gap: 5px;
    flex: 1;
    min-width: 0;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 4px 7px;
  }

  .search-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 12px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    flex: 1;
    min-width: 0;
  }
  .search-input::placeholder {
    color: var(--text-muted);
  }

  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    background: none;
    border: 1px solid transparent;
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .icon-btn:hover {
    background: var(--elevated);
    color: var(--text-secondary);
    border-color: var(--border);
  }
  .icon-btn.active {
    color: var(--text-primary);
    border-color: var(--border);
    background: var(--elevated);
  }

  .new-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    flex-shrink: 0;
    background: var(--accent);
    border: 1px solid var(--accent);
    border-radius: var(--r);
    color: var(--accent-contrast-text, var(--bg));
    cursor: pointer;
  }
  .new-btn:hover {
    opacity: 0.8;
  }

  .toolbar-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 11px;
    font-family: var(--font-sans);
    transition: all var(--t-fast);
    flex-shrink: 0;
  }
  .toolbar-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
  .toolbar-btn.active {
    color: var(--accent);
    border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, transparent);
  }

  .bulk-actions {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--border);
    background: var(--elevated);
    flex-shrink: 0;
  }

  .bulk-count {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-primary);
    margin-right: auto;
  }

  .bulk-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 8px;
    background: none;
    border: 1px solid var(--border);
    border-radius: var(--r);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 11px;
    transition: all var(--t-fast);
  }
  .bulk-btn:hover {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }
  .bulk-btn.danger {
    color: var(--error);
    border-color: color-mix(in srgb, var(--error) 25%, transparent);
  }
  .bulk-btn.danger:hover {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 6%, transparent);
  }

  .list-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-light);
    flex-shrink: 0;
  }
  .sep {
    color: var(--border);
  }

  .list-scroll {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
  }
  .list-scroll:not(.scroll-ready) {
    visibility: hidden;
  }

  .tree-wrap {
    padding: 4px 0;
  }

  .empty-msg {
    padding: 32px 16px;
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
  }

  .load-more-btn {
    display: block;
    width: 100%;
    padding: 10px 12px;
    margin-top: 4px;
    border: none;
    border-top: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    text-align: center;
  }
  .load-more-btn:hover:not(:disabled) {
    color: var(--text);
    background: var(--hover-bg, rgba(128, 128, 128, 0.08));
  }
  .load-more-btn:disabled {
    opacity: 0.6;
    cursor: default;
  }

  /* ── Tree rows ── */
  .tree-row {
    display: flex;
    align-items: center;
    gap: 5px;
    padding-right: 8px;
    height: 26px;
    cursor: pointer;
    user-select: none;
    border-radius: 3px;
    margin: 0 4px;
    transition: background var(--t-fast);
    min-width: 0;
  }
  .tree-row:hover {
    background: var(--hover);
  }
  .file-row.active {
    background: var(--elevated);
  }

  .chevron {
    color: var(--text-muted);
    display: flex;
    align-items: center;
    flex-shrink: 0;
    transition: transform var(--t-fast);
  }
  .chevron.open {
    transform: rotate(90deg);
  }

  .t-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 16px;
    height: 16px;
  }
  .file-icon {
    opacity: 0.9;
  }

  .t-name {
    font-size: 12px;
    font-family: var(--font-sans);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
    color: var(--text-secondary);
  }
  .file-row.active .t-name {
    color: var(--text-primary);
  }

  .t-count {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    flex-shrink: 0;
  }

  /* ── Resize handle ── */
  /* Moved to app.css for global consistency */

  .editor-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow-y: auto;
    background: var(--bg);
    min-width: 0;
  }

  /* ── Empty Dashboard ── */
  .empty-dashboard {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: start;
    min-height: 100%;
    gap: 30px;
    padding: 60px 40px;
    background: var(--bg);
    color: var(--text-primary);
  }
  .dash-search-container {
    width: 100%;
    max-width: 850px;
  }
  .dash-search {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 18px;
    border-radius: var(--r);
    background: var(--surface);
    border: 1px solid var(--border);
    transition: all var(--t-fast);
  }
  .dash-search:focus-within {
    border-color: var(--xp);
    transform: translateY(-1px);
  }
  .dash-search input {
    border: none;
    background: transparent;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    flex: 1;
  }

  .dash-widgets {
    display: grid;
    grid-template-columns: 1fr 1.2fr;
    gap: 24px;
    width: 100%;
    max-width: 850px;
  }
  .dash-quick-capture {
    width: 100%;
    max-width: 850px;
  }
  .dash-widget {
    background: var(--surface);
    border: 1px solid var(--border-light);
    border-radius: var(--r);
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    min-width: 0;
  }
  .quick-note-widget {
    min-width: 0;
    overflow: hidden;
  }
  .dash-action-buttons {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .dash-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0 20px;
    border-radius: var(--r);
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 13px;
    font-family: var(--font-sans);
    transition: all var(--t-fast);
    height: 42px;
  }
  .primary-dash-btn {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
    font-weight: 600;
  }
  .primary-dash-btn:hover {
    background: var(--xp-2);
    border-color: var(--xp-2);
    transform: translateY(-1px);
  }

  .secondary-dash-btn {
    background: color-mix(in srgb, var(--xp-2) 16%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 45%, transparent);
    color: var(--text-primary);
  }
  .secondary-dash-btn:hover {
    background: color-mix(in srgb, var(--xp-2) 28%, transparent);
    border-color: var(--xp-2);
  }
  .daily-note-btn {
    height: auto;
    min-height: 42px;
    padding: 10px 20px;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
  }
  .daily-note-main {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .daily-note-btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    background: color-mix(in srgb, var(--xp-2) 10%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 25%, transparent);
    color: var(--text-disabled);
    transform: none;
  }
  .daily-note-btn:disabled:hover {
    background: color-mix(in srgb, var(--xp-2) 10%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 25%, transparent);
    transform: none;
  }
  .daily-note-muted {
    opacity: 0.45;
    cursor: pointer;
    background: color-mix(in srgb, var(--xp-2) 10%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 25%, transparent);
    color: var(--text-disabled);
  }
  .daily-note-muted:hover {
    background: color-mix(in srgb, var(--xp-2) 18%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 35%, transparent);
  }
  .daily-note-hint {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .momentary-btn {
    background: color-mix(in srgb, var(--xp-3) 14%, transparent);
    border-color: color-mix(in srgb, var(--xp-3) 45%, transparent);
    color: var(--text-secondary);
    border-style: solid;
  }
  .momentary-btn:hover {
    background: color-mix(in srgb, var(--xp-3) 24%, transparent);
    border-color: var(--xp-3);
    color: var(--text-primary);
  }

  .dash-divider {
    height: 1px;
    background: var(--border-light);
    margin: 5px 0;
  }

  .recent-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .recent-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: var(--bg);
    border: 1px solid var(--border-light);
    border-radius: 6px;
    cursor: pointer;
    transition: all var(--t-fast);
    text-align: left;
    min-width: 0;
    width: 100%;
  }
  .recent-item:hover {
    border-color: var(--border);
    background: var(--surface);
  }
  .recent-name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    font-size: 12px;
    color: var(--text-secondary);
    white-space: nowrap;
  }
  .recent-name-text {
    display: inline-block;
    white-space: nowrap;
    transform: translateX(0);
    will-change: transform;
  }
  .recent-name-text.is-overflowing {
    animation: recent-name-marquee var(--scroll-duration, 8s) ease-in-out infinite alternate;
  }
  @keyframes recent-name-marquee {
    from {
      transform: translateX(0);
    }
    to {
      transform: translateX(calc(var(--scroll-distance, 0px) * -1));
    }
  }
  .recent-time {
    font-size: 10px;
    color: var(--text-disabled);
    font-family: var(--font-mono);
  }

  .scratchpad {
    width: 100%;
    height: 100px;
    resize: none;
    background: var(--bg);
    border: 1px solid var(--border-light);
    border-radius: 4px;
    padding: 10px;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 13px;
    outline: none;
    transition: border-color var(--t-fast);
  }

  /* Folder settings button */
  .folder-settings-btn {
    display: none;
    padding: 2px;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    border-radius: 3px;
    margin-left: 4px;
  }
  .folder-row:hover .folder-settings-btn,
  .file-row:hover .folder-settings-btn {
    display: flex;
  }
  .folder-settings-btn:hover {
    color: var(--accent);
    background: var(--border-light);
  }

  /* Folder customize modal */
  .folder-modal-backdrop {
    position: fixed;
    top: 50px;
    bottom: 50px;
    left: 0;
    right: 0;
    z-index: var(--z-overlay);
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .folder-modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    width: 100%;
    height: 100%;
    max-width: 800px;
    min-height: 0;
  }
  .folder-modal-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
  .folder-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .folder-color-row {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }
  .folder-color-input {
    flex: 1;
    height: 28px;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    background: none;
  }
  .folder-color-input::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  .folder-color-input::-webkit-color-swatch {
    border: none;
    border-radius: 3px;
  }
  .folder-hex-input {
    width: 75px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text-primary);
    font-size: 11px;
    text-align: center;
    text-transform: uppercase;
  }
  .folder-icon-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }
  .folder-icon-header {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .folder-search-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .folder-search-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 12px;
    color: var(--text-primary);
    width: 100%;
  }
  .folder-search-input::placeholder {
    color: var(--text-muted);
  }
  .no-icons-msg {
    grid-column: 1 / -1;
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    padding: 20px;
  }
  .folder-icon-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: 6px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    align-content: start;
  }
  .folder-icon-btn {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    background: var(--bg);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .folder-icon-btn:hover {
    border-color: var(--border);
    color: var(--text-primary);
  }
  .folder-icon-btn.selected {
    border-color: var(--xp);
    color: var(--xp);
    background: color-mix(in srgb, var(--xp) 12%, transparent);
  }
  .folder-modal-btns {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }
  .folder-modal-btns button {
    flex: 1;
    padding: 8px;
    border-radius: 5px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-secondary);
  }
  .folder-modal-btns button:first-child:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }
  .folder-modal-btns button:last-child {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
  }
  .folder-modal-btns button:last-child:hover {
    opacity: 0.85;
  }

  /* ── Delete confirmation bar ── */
  .delete-confirm-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
  }
  .delete-confirm-text {
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 500;
  }
  .delete-confirm-hint {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    flex: 1;
  }
  .delete-confirm-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .delete-confirm-actions .btn-cancel,
  .delete-confirm-actions .btn-danger {
    padding: 6px 14px;
    border-radius: var(--r);
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-secondary);
    font-family: var(--font-sans);
    transition: all var(--t-fast);
  }
  .delete-confirm-actions .btn-cancel:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }
  .delete-confirm-actions .btn-danger {
    background: var(--error);
    border-color: var(--error);
    color: #fff;
  }
  .delete-confirm-actions .btn-danger:hover {
    opacity: 0.85;
  }

  /* ── Responsive ── */

  /* Tablet — narrow the list panel */
  @media (max-width: 1024px) {
    .notes-page {
      grid-template-columns: minmax(200px, 240px) 5px 1fr;
    }
  }

  @media (max-width: 768px) {
    .notes-page {
      grid-template-columns: 1fr;
      grid-template-rows: auto;
    }

    .notes-list {
      max-height: none;
      border-bottom: 1px solid var(--border);
      overflow: visible;
    }

    .resize-handle {
      display: none;
    }

    .editor-panel {
      height: auto;
      overflow: visible;
    }

    .empty-dashboard {
      padding: var(--s4) var(--s3);
      gap: var(--s4);
    }

    .dash-widgets {
      grid-template-columns: 1fr;
      gap: var(--s3);
    }

    .dash-widget {
      padding: var(--s3);
    }

    .dash-search-container {
      max-width: 100%;
    }

    .dash-search {
      padding: var(--s2) var(--s3);
    }

    .sort-menu {
      width: 180px;
    }

    .folder-modal-backdrop {
      top: 0;
      bottom: 0;
    }

    .folder-modal {
      max-width: 100%;
      padding: var(--s3);
    }
  }

  @media (max-width: 480px) {
    .notes-list {
      max-height: none;
    }

    .empty-dashboard {
      padding: var(--s3) var(--s2);
      gap: var(--s3);
    }

    .dash-widget {
      padding: var(--s2);
    }

    .list-toolbar {
      padding: var(--s1) var(--s2);
    }

    .tree-actions-bar {
      padding: var(--s1) var(--s2);
    }

    .list-meta {
      padding: var(--s1) var(--s2);
    }
  }

  @media (max-width: 360px) {
    .notes-list {
      max-height: 35vh;
    }
    .sort-menu {
      width: 130px;
    }
    .empty-dashboard {
      padding: var(--s3) var(--s2);
    }
    .dash-widget {
      padding: var(--s2);
    }
    .folder-modal {
      padding: var(--s2);
    }
  }
</style>
