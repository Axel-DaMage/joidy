<script lang="ts">
  import { onMount, onDestroy, tick } from 'svelte';
  import { page } from '$app/stores';
  import { notes, loadNotes } from '$lib/stores/notes';
  import { api } from '$lib/api';
  import { loadUserSettings } from '$lib/utils/userSettings';
  import { getSnapshot } from '$lib/stores/pageSnapshots';
  import {
    search,
    viewMode,
    sortMode,
    collapsed,
    allCollapsed,
    panelWidth,
    notesPrefsReady,
    selectedNote,
    showEditor,
    editingNew,
    dailyInitialTitle,
    dailyNotesConfigured,
    vaultPath,
    totalNotes,
    deleteModalOpen,
    __treeScrollTop,
    __listScrollTop,
  } from '$lib/stores/notesUi';
  import {
    isSortMode,
    loadFolders,
    openNote,
    openNew,
    ensureNoteEditor,
    captureNotesSnapshot,
    persist,
  } from '$lib/utils/notesPage';
  import NotesToolbar from '$lib/components/NotesToolbar.svelte';
  import NotesListBody from '$lib/components/NotesListBody.svelte';
  import NotesOverlays from '$lib/components/NotesOverlays.svelte';
  import NotesEditorPanel from '$lib/components/NotesEditorPanel.svelte';
  import NotesDeleteModal from '$lib/components/NotesDeleteModal.svelte';

  // Resizable panel — min width matches the dashboard's default panel width
  // so the left sidebar (plant, timer, etc.) on the index page is never
  // crushed below its intended size. Moving right is unrestricted up to MAX_W.
  const MIN_W = 260;
  const MAX_W = 520;
  let dragging = false;

  $: showNew = $page.url.searchParams.get('new') === '1';
  $: selectedId = $page.url.searchParams.get('id');
  $: urlSearch = $page.url.searchParams.get('search');

  // Handle URL changes reactively
  $: if (urlSearch !== null) {
    $search = urlSearch;
  }

  $: if (showNew && $notesPrefsReady) {
    const urlTitle = $page.url.searchParams.get('title');
    if (!$editingNew || $dailyInitialTitle !== (urlTitle ?? '')) {
      openNew();
      if (urlTitle) {
        $dailyInitialTitle = urlTitle;
      }
    }
  }

  $: if (selectedId && $notes.length > 0) {
    const n = $notes.find((n) => String(n.id) === selectedId);
    if (n && $selectedNote?.id !== n.id) {
      openNote(n);
    }
  } else if (!selectedId && $showEditor && !$editingNew) {
    // If we were viewing a note and ID cleared, close editor
    $showEditor = false;
    $selectedNote = null;
  }

  onMount(async () => {
    // Load prefs from localStorage FIRST (synchronous) — before any async
    // operation so we know the target scroll position ASAP.
    const saved = loadUserSettings().notesUi;
    if (saved?.panelWidth !== undefined) {
      $panelWidth = Math.max(MIN_W, Math.min(MAX_W, Number(saved.panelWidth)));
    }
    if (isSortMode(saved?.sortMode)) {
      $sortMode = saved.sortMode;
    }
    if (saved?.viewMode === 'tree' || saved?.viewMode === 'list') {
      $viewMode = saved.viewMode;
    }
    if (typeof saved?.search === 'string') {
      $search = saved.search;
    }
    if (Array.isArray(saved?.collapsedPaths)) {
      $collapsed = new Set(saved.collapsedPaths.filter((p) => typeof p === 'string'));
    }
    $allCollapsed = Boolean(saved?.allCollapsed);
    if (Number.isFinite(Number(saved?.treeScrollTop))) {
      __treeScrollTop.set(Number(saved?.treeScrollTop));
    }
    if (Number.isFinite(Number(saved?.listScrollTop))) {
      __listScrollTop.set(Number(saved?.listScrollTop));
    }

    const snap = getSnapshot('/notes');
    if (snap) {
      $search = snap.state.search ?? '';
      $viewMode = snap.state.viewMode ?? 'tree';
      $sortMode = snap.state.sortMode ?? 'edit-new';
      $allCollapsed = snap.state.allCollapsed ?? false;
      if (snap.state.collapsedPaths) $collapsed = new Set(snap.state.collapsedPaths);
      if (snap.state.selectedNoteId) selectedId = String(snap.state.selectedNoteId);
    }

    $notesPrefsReady = true;

    // Kick off note loading (loads from cache synchronously inside loadNotes,
    // then fetches from API asynchronously).
    loadNotes();
    loadFolders();

    // Fire async config/stats fetches in parallel (non-blocking).
    api.config
      .get()
      .then((config) => {
        $vaultPath = (config.obsidian_vault_path || '').trim();
        $dailyNotesConfigured = Boolean(
          config.obsidian_vault_path?.trim() && config.daily_notes_folder?.trim()
        );
      })
      .catch(() => {
        $dailyNotesConfigured = false;
      });

    api.stats
      .system()
      .then((stats) => {
        $totalNotes = stats.notes;
      })
      .catch(() => {
        $totalNotes = 0;
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
    captureNotesSnapshot();
  }

  // ── Resize ──
  function startResize(e: MouseEvent) {
    e.preventDefault();
    dragging = true;
    const startX = e.clientX;
    const startW = $panelWidth;
    function onMove(e: MouseEvent) {
      $panelWidth = Math.max(MIN_W, Math.min(MAX_W, startW + (e.clientX - startX)));
    }
    function onUp() {
      dragging = false;
      if ($notesPrefsReady) persist();
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    }
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && deleteModalOpen.set(false)} />

<div class="notes-page" class:dragging style="--panel-w: {$panelWidth}px">
  <!-- ── List / Tree panel ─────────────────────────────────────────────────── -->
  <aside class="notes-list">
    <NotesToolbar />
    <NotesListBody />
  </aside>

  <NotesOverlays />

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="resize-handle"
    role="separator"
    aria-orientation="vertical"
    aria-label="Resize panel"
    onmousedown={startResize}
  ></div>

  <!-- ── Editor panel ──────────────────────────────────────────────────────── -->
  <NotesEditorPanel />
</div>

<NotesDeleteModal />

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

  /* ── Resize handle ── */
  /* Moved to app.css for global consistency */
</style>
