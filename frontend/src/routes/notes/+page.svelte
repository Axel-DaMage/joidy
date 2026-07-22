<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Search, Plus, X, List, FolderTree, ChevronRight, FileEdit, FolderPlus, ChevronsUpDown, ArrowUpDown, Settings } from 'lucide-svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import NoteEditor from '$lib/components/NoteEditor.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import IconPicker from '$lib/components/IconPicker.svelte';
  import VirtualList from '$lib/components/VirtualList.svelte';
  import { notes, notesLoading, loadNotes, createNote, updateNote, deleteNote, aiSuggestions, notesLoadedOnce } from '$lib/stores/notes';
  import { buildTree, flattenTree, extractFrontmatter, getFileIcon, type SortMode, type FlatNode } from '$lib/utils/fileTree';
  import TreeContextMenu from '$lib/components/TreeContextMenu.svelte';
  import FolderPicker from '$lib/components/FolderPicker.svelte';
  import { showHiddenFiles, showTrash, folderMetaStore, updateFolderMeta } from '$lib/stores/settings';
  import { loadUserSettings, patchUserSettings } from '$lib/utils/userSettings';
  import { captureSnapshot, getSnapshot } from '$lib/stores/pageSnapshots';
  import { api, type Note } from '$lib/api';

  // ── State ────────────────────────────────────────────────────────────────────
  let search = '';
  let selectedNote: Note | null = null;
  let showEditor = false;
  let editingNew = false;
  let viewMode: 'tree' | 'list' = 'list';
  let dailySourcePath: string | null = null;
  let dailyInitialTitle = '';
  let dailyNotesConfigured = false;
  let deleteConfirm = false;

  // Folder customization
  let editingFolder: string | null = null;
  let folderColor = '#c8a96e';
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
    if (!renamingNode || !renameValue.trim()) { renamingNode = null; return; }
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
    if (!node || !node.note) { movingNode = null; return; }
    const note = node.note;
    movingNode = null;
    const newPath = targetPath ? `${targetPath}/${node.name}` : node.name;
    await api.notes.update(note.id, { source_path: newPath });
    await loadNotes();
  }

  function handleDeleteNote() {
    if (!ctxMenu || !ctxMenu.node.note) { ctxMenu = null; return; }
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
      const ids = $notes.filter(n => n.source_path && n.source_path.includes(path)).map(n => n.id);
      Promise.all(ids.map(id => deleteNote(id))).then(() => loadNotes());
    }
  }

  let newFolderName = "";
  let newFolderParent = "";
  let newFolderIcon = "Folder";
  let newFolderColor = "#c8a96e";
  async function openFolderCustomizer(node: { path: string; color?: string | null; icon?: string | null; note?: Note }) {
    editingFolder = node.path;
    folderColor = node.color || '#c8a96e';
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
      }
    };
  }

  function isSortMode(value: unknown): value is SortMode {
    return typeof value === 'string' && SORT_MODES.includes(value as SortMode);
  }

  function persistNotesPrefs() {
    const currentScroll = listScrollEl?.scrollTop ?? 0;
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
      }
    });
  }

  function setSortMode(mode: SortMode) {
    sortMode = mode;
    showSortMenu = false;
    if (notesPrefsReady) persistNotesPrefs();
  }

    function handleCreateFolder() {
    creatingFolder = true;
    newFolderName = "";
    newFolderParent = "";
    newFolderIcon = "Folder";
    newFolderColor = "#c8a96e";
  }

  function toggleCollapseAll() {
    allCollapsed = !allCollapsed;
    if (allCollapsed) {
      const folders = flatNodes.filter(n => n.type === 'folder');
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

  // Resizable panel
  const MIN_W = 160;
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
    const n = $notes.find(n => String(n.id) === selectedId);
    if (n && selectedNote?.id !== n.id) {
      openNote(n);
    }
  } else if (!selectedId && showEditor && !editingNew) {
    // If we were viewing a note and ID cleared, close editor
    showEditor = false;
    selectedNote = null;
  }

  // Flat filtered list for list mode
  $: filtered = $notes.filter(n =>
    !search ||
    n.title.toLowerCase().includes(search.toLowerCase()) ||
    n.tags.some(t => t.includes(search.toLowerCase()))
  );

  $: editorNote = editingNew
    ? (isMomentary ? ({ ...momentaryDraft, id: -1, source: 'momentary' } as Note) : null)
    : selectedNote;

  // Tree → flat list (no recursive component, avoids Svelte 5 HMR issues)
  $: tree = buildTree($notes, viewMode === 'tree' ? search : '', $showTrash, $showHiddenFiles, sortMode, $folderMetaStore);
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
    if (historyIndex >= 0 && historyIndex < historyStack.length - 1 && historyStack[historyIndex + 1] === id) {
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
      const n = $notes.find(n => n.id === id);
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
      const n = $notes.find(n => n.id === id);
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
    tick().then(() => {
      if (!listScrollEl) return;
      listScrollEl.scrollTop = viewMode === 'tree' ? treeScrollTop : listScrollTop;
    });
  }

  onMount(async () => {
    try {
      const config = await api.config.get();
      dailyNotesConfigured = Boolean(config.obsidian_vault_path?.trim() && config.daily_notes_folder?.trim());
    } catch {
      dailyNotesConfigured = false;
    }

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
    treeScrollTop = Number.isFinite(Number(saved?.treeScrollTop)) ? Number(saved?.treeScrollTop) : 0;
    listScrollTop = Number.isFinite(Number(saved?.listScrollTop)) ? Number(saved?.listScrollTop) : 0;
    notesPrefsReady = true;

    const snap = getSnapshot('/notes');
    if (snap) {
      search = snap.state.search ?? '';
      viewMode = snap.state.viewMode ?? 'tree';
      sortMode = snap.state.sortMode ?? 'edit-new';
      allCollapsed = snap.state.allCollapsed ?? false;
      if (snap.state.collapsedPaths) collapsed = new Set(snap.state.collapsedPaths);
      if (snap.state.selectedNoteId) selectedId = snap.state.selectedNoteId;
    }

    loadNotes();

    requestAnimationFrame(async () => {
      await tick();
      if (showNew) openNew();
      if (selectedId) {
        const n = $notes.find(n => String(n.id) === selectedId);
        if (n) openNote(n);
      } else if (typeof saved?.selectedNoteId === 'number') {
        const n = $notes.find(note => note.id === saved.selectedNoteId);
        if (n) openNote(n);
      }
      await tick();
      if (listScrollEl) {
        const snapScroll = snap?.scrollPositions;
        listScrollEl.scrollTop = snapScroll?.['notes-list'] ?? (viewMode === 'tree' ? treeScrollTop : listScrollTop);
      }
    });

    window.addEventListener('beforeunload', handleBeforeUnload);
  });

  function handleBeforeUnload() {
    captureSnapshot('/notes', 
      { search, viewMode, sortMode, allCollapsed, collapsedPaths: Array.from(collapsed), selectedNoteId: selectedNote?.id },
      [{ id: 'notes-list', scrollTop: listScrollEl?.scrollTop ?? 0 }]
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
    if (viewMode === 'tree') treeScrollTop = listScrollEl.scrollTop;
    else listScrollTop = listScrollEl.scrollTop;
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
  }

  function openNew() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = false;
    dailySourcePath = null;
    dailyInitialTitle = '';
    aiSuggestions.set([]);
  }

  function openMomentary() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = true;
    dailySourcePath = null;
    dailyInitialTitle = '';
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
      if (n) { selectedNote = n; editingNew = false; }
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
  let calcInput = '';
  let calcResult = '0';
  let lastResult = '';
  function evaluateCalc() {
    try {
      if (!calcInput.trim()) { calcResult = '0'; return; }
      
      let expr = calcInput
        .replace(/sin\(/g, 'Math.sin(')
        .replace(/cos\(/g, 'Math.cos(')
        .replace(/tan\(/g, 'Math.tan(')
        .replace(/log\(/g, 'Math.log10(')
        .replace(/ln\(/g, 'Math.log(')
        .replace(/√\(/g, 'Math.sqrt(')
        .replace(/π/g, 'Math.PI')
        .replace(/e/g, 'Math.E')
        .replace(/\^/g, '**')
        .replace(/(\d+)!/g, (match, n) => {
          let f = 1; for(let i=1; i<=+n; i++) f*=i; return f+'';
        })
        .replace(/Ans/g, lastResult || '0')
        .replace(/÷/g, '/')
        .replace(/×/g, '*');
      
      const sanitize = expr.replace(/[^0-9+\-*/(). Math[a-z0-9]!]/g, '');
      const res = new Function('return ' + sanitize)();
      if (typeof res === 'number') {
        calcResult = Number(res.toFixed(8)).toString();
      } else {
        calcResult = res + '';
      }
    } catch {
      calcResult = '...';
    }
  }

  function addCalc(val: string) {
    if (val === '=') { 
      evaluateCalc(); 
      if (calcResult !== '...') lastResult = calcResult;
      return; 
    }
    if (val === 'AC') { calcInput = ''; calcResult = '0'; return; }
    if (val === 'Ans') { calcInput += 'Ans'; evaluateCalc(); return; }
    if (val === 'x!') { calcInput += '!'; evaluateCalc(); return; }
    if (val === 'xy') { calcInput += '^'; evaluateCalc(); return; }
    if (val === '√') { calcInput += '√('; evaluateCalc(); return; }
    
    // Auto-parenthesis for functions
    if (['sin', 'cos', 'tan', 'log', 'ln'].includes(val)) {
      calcInput += val + '(';
    } else {
      calcInput += val;
    }
    evaluateCalc();
  }

  function quickNoteFromScratch() {
    openNew();
    // We can't easily pre-fill NoteEditor here without more store logic, 
    // but the user just wants the "normal" creation flow to be the priority.
  }
</script>

<svelte:window on:click={() => { if (showSortMenu) showSortMenu = false; }} on:keydown={(e) => e.key === 'Escape' && (deleteConfirm = false)} />

<div
  class="notes-page"
  class:dragging
  style="--panel-w: {panelWidth}px"
>
  <!-- ── List / Tree panel ─────────────────────────────────────────────────── -->
  <aside class="notes-list">
    <div class="tree-actions-bar">
      <div class="actions-left">
        <button class="icon-btn" title="Crear nota" on:click={openNew}><FileEdit size={13} /></button>
        <button class="icon-btn" title="Crear carpeta" on:click={handleCreateFolder}><FolderPlus size={13} /></button>
        <div class="sort-wrapper">
          <button class="icon-btn" title="Cambiar orden" on:click|stopPropagation={() => showSortMenu = !showSortMenu}>
            <ArrowUpDown size={13} />
          </button>
          {#if showSortMenu}
            <div class="sort-menu" on:click|stopPropagation>
              <button class="sort-btn" class:active={sortMode==='az'} on:click={() => setSortMode('az')}>Ordenar por nombre (A-Z)</button>
              <button class="sort-btn" class:active={sortMode==='za'} on:click={() => setSortMode('za')}>Ordenar por nombre (Z-A)</button>
              <div class="sort-divider"></div>
              <button class="sort-btn" class:active={sortMode==='edit-new'} on:click={() => setSortMode('edit-new')}>Editar (más reciente) {#if sortMode==='edit-new'}✓{/if}</button>
              <button class="sort-btn" class:active={sortMode==='edit-old'} on:click={() => setSortMode('edit-old')}>Editar (más antiguo) {#if sortMode==='edit-old'}✓{/if}</button>
              <div class="sort-divider"></div>
              <button class="sort-btn" class:active={sortMode==='create-new'} on:click={() => setSortMode('create-new')}>Creado (nuevo-antiguo) {#if sortMode==='create-new'}✓{/if}</button>
              <button class="sort-btn" class:active={sortMode==='create-old'} on:click={() => setSortMode('create-old')}>Creado (antiguo-nuevo) {#if sortMode==='create-old'}✓{/if}</button>
            </div>
          {/if}
        </div>
        <button class="icon-btn" title={allCollapsed ? "Expandir todo" : "Comprimir todo"} on:click={toggleCollapseAll}>
          <ChevronsUpDown size={13} />
        </button>
      </div>

    </div>

    <div class="list-toolbar">
      <div class="search-wrap">
        <Search size={11} style="color: var(--text-muted); flex-shrink:0;" />
        <input class="search-input" bind:value={search} placeholder="Buscar..." />
        {#if search}
          <button class="icon-btn" on:click={() => search = ''} title="Limpiar">
            <X size={10} />
          </button>
        {/if}
      </div>
    </div>

    <div class="list-meta">
      <span>{$notes.length} notas</span>
      {#if search}<span class="sep">·</span><span>{filtered.length} resultados</span>{/if}
    </div>

    <div class="list-scroll" bind:this={listScrollEl} on:scroll={onListScroll}>
      {#if $notesLoading}
        <div class="empty-msg">Cargando...</div>

      {:else if viewMode === 'tree'}
        {#if flatNodes.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else if flatNodes.length > 50}
            <VirtualList items={flatNodes} itemHeight={26} getKey={(n, i) => n.path ?? i} let:item let:index>
              {#if item.type === 'folder'}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row folder-row"
                  style="padding-left: {8 + item.depth * 14}px"
                  on:click={() => toggleFolder(item.path)}
                  on:contextmenu={(e) => handleContextMenu(e, item)}
                >
                  <span class="chevron" class:open={!collapsed.has(item.path)}>
                    <ChevronRight size={11} />
                  </span>
                  <div class="t-icon"><DynamicIcon name={item.icon} size={13} color={item.color} pack={item.pack} /></div>
                  <span class="t-name folder-name">{item.name}</span>
                  <button class="folder-settings-btn" title="Personalizar carpeta" on:click|stopPropagation={() => openFolderCustomizer(item)}>
                    <Settings size={10} />
                  </button>
                  <span class="t-count">{item.childCount}</span>
                </div>
              {:else}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row file-row"
                  class:active={item.note?.id === selectedNote?.id}
                  style="padding-left: {20 + item.depth * 14}px"
                  on:click={() => item.note && openNote(item.note)}
                  on:contextmenu={(e) => handleContextMenu(e, item)}
                >
                  <div class="t-icon file-icon"><DynamicIcon name={item.icon} size={11} color={item.color} pack={item.pack} /></div>
                  <span class="t-name file-name">{item.name}</span>
                  <button class="folder-settings-btn" title="Personalizar nota" on:click|stopPropagation={() => openFolderCustomizer({ path: item.note?.source_path || item.path, icon: item.icon, color: item.color, note: item.note })}>
                    <Settings size={10} />
                  </button>
                </div>
              {/if}
            </VirtualList>
        {:else}
          <div class="tree-wrap">
            {#each flatNodes as node (node.path)}
              {#if node.type === 'folder'}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row folder-row"
                  style="padding-left: {8 + node.depth * 14}px"
                  on:click={() => toggleFolder(node.path)}
                  on:contextmenu={(e) => handleContextMenu(e, node)}
                >
                  <span class="chevron" class:open={!collapsed.has(node.path)}>
                    <ChevronRight size={11} />
                  </span>
                  <div class="t-icon"><DynamicIcon name={node.icon} size={13} color={node.color} pack={node.pack} /></div>
                  <span class="t-name folder-name">{node.name}</span>
                  <button class="folder-settings-btn" title="Personalizar carpeta" on:click|stopPropagation={() => openFolderCustomizer(node)}>
                    <Settings size={10} />
                  </button>
                  <span class="t-count">{node.childCount}</span>
                </div>
              {:else}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row file-row"
                  class:active={node.note?.id === selectedNote?.id}
                  style="padding-left: {20 + node.depth * 14}px"
                  on:click={() => node.note && openNote(node.note)}
                  on:contextmenu={(e) => handleContextMenu(e, node)}
                >
                  <div class="t-icon file-icon"><DynamicIcon name={node.icon} size={11} color={node.color} pack={node.pack} /></div>
                  <span class="t-name file-name">{node.name}</span>
                  <button class="folder-settings-btn" title="Personalizar nota" on:click|stopPropagation={() => openFolderCustomizer({ path: node.note?.source_path || node.path, icon: node.icon, color: node.color, note: node.note })}>
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
          <VirtualList items={filtered} itemHeight={52} let:item let:index>
            <NoteCard note={item} active={selectedNote?.id === item.id} on:select={(e) => openNote(e.detail)} on:customize={(e) => openFolderCustomizer(e.detail)} />
          </VirtualList>
        {:else}
          {#each filtered as note}
            <NoteCard {note} active={selectedNote?.id === note.id} on:select={(e) => openNote(e.detail)} on:customize={(e) => openFolderCustomizer(e.detail)} />
          {/each}
        {/if}
      {/if}
    </div>
  </aside>

  <!-- Folder customize modal -->
  <!-- Create folder modal -->
  {#if creatingFolder}
    <div class="folder-modal-backdrop" on:click={() => creatingFolder = false}>
      <div class="folder-modal" on:click|stopPropagation>
        <h3 class="folder-modal-title">Crear carpeta</h3>
        
        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
          <span class="folder-label mono">Nombre</span>
          <input type="text" class="input mono" bind:value={newFolderName} placeholder="Nueva Carpeta" style="width:100%; box-sizing:border-box;" />
        </div>
        
        <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
          <span class="folder-label mono">Ubicación (Padre)</span>
          <select class="input mono" bind:value={newFolderParent} style="width:100%; box-sizing:border-box;">
            <option value="">(Raíz)</option>
            {#each flatNodes.filter(n => n.type === 'folder') as f}
              <option value={f.path}>{f.path}</option>
            {/each}
          </select>
        </div>

        <div class="folder-color-row">
          <span class="folder-label mono">Color</span>
          <input type="color" class="folder-color-input" bind:value={newFolderColor} />
          <input type="text" class="folder-hex-input mono" maxlength="7" bind:value={newFolderColor} />
        </div>
        
        <div class="folder-icon-row">
          <span class="folder-label mono">Icono</span>
          <IconPicker selected={newFolderIcon} color={newFolderColor} onSelect={(ic) => newFolderIcon = ic} />
        </div>
        
        <div class="folder-modal-btns">
          <button on:click={() => creatingFolder = false}>Cancelar</button>
          <button class="primary" disabled={!newFolderName.trim()} on:click={async () => {
            if (!newFolderName.trim()) return;
            const targetPath = newFolderParent ? `${newFolderParent}/${newFolderName.trim()}` : newFolderName.trim();
            try {
              await api.folders.create(targetPath);
              updateFolderMeta(targetPath, { icon: newFolderIcon, color: newFolderColor });
              creatingFolder = false;
              // Refresh tree
              const ns = await api.notes.list();
              notes.set(ns);
            } catch (e) {
              alert((e as any).message || "Error al crear carpeta");
            }
          }}>Crear</button>
        </div>
      </div>
    </div>
  {/if}

  {#key ctxMenu}
    {#if ctxMenu}
      <TreeContextMenu x={ctxMenu.x} y={ctxMenu.y} node={ctxMenu.node}
        on:close={() => ctxMenu = null}
        on:rename={handleRename}
        on:move={handleMove}
        on:deleteNote={handleDeleteNote}
        on:newNoteInFolder={handleNewNoteInFolder}
        on:deleteFolder={handleDeleteFolder}
      />
    {/if}
  {/key}

  {#if renamingNode}
    <div class="folder-modal-backdrop" on:click={() => renamingNode = null}>
      <div class="folder-modal" on:click|stopPropagation>
        <h3 class="folder-modal-title">Renombrar</h3>
        <input type="text" class="input mono" bind:value={renameValue} style="width:100%; box-sizing:border-box; margin-bottom:12px;" on:keydown={(e) => e.key === 'Enter' && confirmRename()} />
        <div class="folder-modal-btns">
          <button on:click={() => renamingNode = null}>Cancelar</button>
          <button class="primary" disabled={!renameValue.trim()} on:click={confirmRename}>Guardar</button>
        </div>
      </div>
    </div>
  {/if}

  {#if movingNode}
    <FolderPicker
      flatNodes={flatNodes}
      on:close={() => movingNode = null}
      on:select={(e) => confirmMove(e.detail)}
    />
  {/if}

  {#if editingFolder}
    <div class="folder-modal-backdrop" on:click={() => editingFolder = null}>
      <div class="folder-modal" on:click|stopPropagation>
        <h3 class="folder-modal-title">Personalizar carpeta</h3>
        
        <!-- Color bar -->
        <div class="folder-color-row">
          <span class="folder-label mono">Color</span>
          <input type="color" class="folder-color-input" bind:value={folderColor} />
          <input type="text" class="folder-hex-input mono" maxlength="7" bind:value={folderColor} />
        </div>
        
        <!-- Icon picker -->
        <div class="folder-icon-row">
          <span class="folder-label mono">Icono</span>
          <IconPicker selected={folderIcon} color={folderColor} onSelect={(ic) => folderIcon = ic} />
        </div>
        
        <div class="folder-modal-btns">
          <button on:click={() => editingFolder = null}>Cancelar</button>
          <button on:click={async () => { 
            if (editingFolder) {
              updateFolderMeta(editingFolder, { icon: folderIcon, color: folderColor });
              if (editingFolderNote) {
                let content = editingFolderNote.content;
                const match = content.match(/^---\n([\s\S]*?)\n---/);
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
                  content = content.replace(/^---\n([\s\S]*?)\n---/, `---\n${yaml}\n---`);
                } else {
                  content = `---\nicon: ${folderIcon}\niconColor: ${folderColor}\n---\n\n${content}`;
                }
                await updateNote(editingFolderNote.id, { content });
              }
            }
            editingFolder = null; 
            editingFolderNote = null;
          }}>Guardar</button>
        </div>
      </div>
    </div>
  {/if}

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="resize-handle" on:mousedown={startResize}></div>

  <!-- ── Editor panel ──────────────────────────────────────────────────────── -->
  <div class="editor-panel">
    {#if deleteConfirm}
      <div class="delete-confirm-bar">
        <span class="delete-confirm-text">¿Eliminar esta nota?</span>
        <span class="delete-confirm-hint">Esta acción no se puede deshacer.</span>
        <div class="delete-confirm-actions">
          <button class="btn-cancel" on:click={() => deleteConfirm = false}>Cancelar</button>
          <button class="btn-danger" on:click={handleDelete}>Eliminar</button>
        </div>
      </div>
    {/if}
    {#if showEditor}
      {#key editingNew ? (isMomentary ? 'momentary' : 'new') : selectedNote?.id}
        <NoteEditor
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
      {/key}
    {:else}
      <div class="empty-dashboard">
        <DynamicIcon name="Box" size={48} color="var(--border)" />
        
        <div class="dash-search-container">
          <div class="dash-search">
            <Search size={14} color="var(--text-muted)" />
            <input type="text" placeholder="Buscar nota en tu baúl..." bind:value={search} />
          </div>
        </div>

        <div class="dash-widgets">
          <!-- Quick Note Area -->
          <div class="dash-widget quick-note-widget">
            <div class="dash-widget-title"><DynamicIcon name="PenTool" size={13}/> Acciones Rápidas</div>
            <div class="dash-action-buttons">
              <button class="dash-btn primary-dash-btn" on:click={openNew}>
                <FileEdit size={16} /> Crear nota nueva
              </button>
              <button class={`dash-btn secondary-dash-btn daily-note-btn ${dailyNotesConfigured ? '' : 'daily-note-muted'}`} on:click={openDaily}>
                <span class="daily-note-main">
                  <DynamicIcon name="Calendar" size={16} /> Nota Diaria
                </span>
                <span class="daily-note-hint">Configurar ruta de nota diaria</span>
              </button>
              <button class="dash-btn secondary-dash-btn momentary-btn" on:click={openMomentary}>
                <Plus size={16} /> Nota Momentánea
              </button>
            </div>
            
            <div class="dash-divider"></div>
            <div class="dash-widget-title"><DynamicIcon name="History" size={13}/> Recientes</div>
            <div class="recent-list">
              {#each $notes.slice(0, 3) as note}
                {@const vis = getNoteVisual(note)}
                <button class="recent-item" on:click={() => openNote(note)}>
                  <DynamicIcon name={vis.icon} size={12} color={vis.color || 'var(--text-disabled)'} pack={vis.pack} />
                  <span class="recent-name" use:autoScrollTitle={note.title}>
                    <span class="recent-name-text">{note.title}</span>
                  </span>
                  <span class="recent-time">{new Date(note.updated_at).toLocaleDateString()}</span>
                </button>
              {/each}
            </div>
          </div>

          <!-- Scientific Calculator -->
          <div class="dash-widget scientific-calc">
            <div class="dash-widget-title" style="margin-bottom: 5px;">
              <DynamicIcon name="Calculator" size={13}/> Calculadora
            </div>
            <div class="calc-display">
              <div class="calc-history"><DynamicIcon name="History" size={10} /></div>
              <input
                class="calc-input"
                bind:value={calcInput}
                on:input={evaluateCalc}
                placeholder="0"
              />
              <div class="calc-res">{calcResult}</div>
            </div>
            <div class="calc-grid">
              <!-- Row 1 -->
              <button class="calc-btn sm" on:click={() => {}}>Deg</button>
              <button class="calc-btn sm" on:click={() => addCalc('x!')}>x!</button>
              <button class="calc-btn sm" on:click={() => addCalc('(')}>(</button>
              <button class="calc-btn sm" on:click={() => addCalc(')')}>)</button>
              <button class="calc-btn sm" on:click={() => addCalc('%')}>%</button>
              <button class="calc-btn sm clear" on:click={() => addCalc('AC')}>AC</button>
              <button class="calc-btn op" on:click={() => addCalc('÷')}>÷</button>
              
              <!-- Row 2 -->
              <button class="calc-btn sm" on:click={() => addCalc('inv')}>Inv</button>
              <button class="calc-btn sm" on:click={() => addCalc('sin')}>sin</button>
              <button class="calc-btn sm" on:click={() => addCalc('ln')}>ln</button>
              <button class="calc-btn num" on:click={() => addCalc('7')}>7</button>
              <button class="calc-btn num" on:click={() => addCalc('8')}>8</button>
              <button class="calc-btn num" on:click={() => addCalc('9')}>9</button>
              <button class="calc-btn op" on:click={() => addCalc('×')}>×</button>

              <!-- Row 3 -->
              <button class="calc-btn sm" on:click={() => addCalc('π')}>π</button>
              <button class="calc-btn sm" on:click={() => addCalc('cos')}>cos</button>
              <button class="calc-btn sm" on:click={() => addCalc('log')}>log</button>
              <button class="calc-btn num" on:click={() => addCalc('4')}>4</button>
              <button class="calc-btn num" on:click={() => addCalc('5')}>5</button>
              <button class="calc-btn num" on:click={() => addCalc('6')}>6</button>
              <button class="calc-btn op" on:click={() => addCalc('-')}>-</button>

              <!-- Row 4 -->
              <button class="calc-btn sm" on:click={() => addCalc('e')}>e</button>
              <button class="calc-btn sm" on:click={() => addCalc('tan')}>tan</button>
              <button class="calc-btn sm" on:click={() => addCalc('√')}>√</button>
              <button class="calc-btn num" on:click={() => addCalc('1')}>1</button>
              <button class="calc-btn num" on:click={() => addCalc('2')}>2</button>
              <button class="calc-btn num" on:click={() => addCalc('3')}>3</button>
              <button class="calc-btn op" on:click={() => addCalc('+')}>+</button>

              <!-- Row 5 -->
              <button class="calc-btn sm" on:click={() => addCalc('Ans')}>Ans</button>
              <button class="calc-btn sm" on:click={() => addCalc('EXP')}>EXP</button>
              <button class="calc-btn sm" on:click={() => addCalc('xy')}>x<sup>y</sup></button>
              <button class="calc-btn num" on:click={() => addCalc('0')}>0</button>
              <button class="calc-btn num" on:click={() => addCalc('.')}>.</button>
              <button class="calc-btn equals" on:click={() => addCalc('=')}>=</button>
              <div></div> <!-- Spacing for grid alignment if needed, or leave empty -->
            </div>
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
  .notes-page.dragging { user-select: none; }
  .notes-page.dragging * { cursor: col-resize !important; }

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
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    z-index: 100;
    display: flex;
    flex-direction: column;
    padding: 4px 0;
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
  .sort-btn:hover { background: var(--hover); color: var(--text-primary); }
  .sort-btn.active { color: var(--accent); font-weight: 500; }

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
  .search-input::placeholder { color: var(--text-muted); }

  .icon-btn {
    display: flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; flex-shrink: 0;
    background: none; border: 1px solid transparent;
    border-radius: var(--r); color: var(--text-muted); cursor: pointer;
    transition: all var(--t-fast);
  }
  .icon-btn:hover { background: var(--elevated); color: var(--text-secondary); border-color: var(--border); }
  .icon-btn.active { color: var(--text-primary); border-color: var(--border); background: var(--elevated); }

  .new-btn {
    display: flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; flex-shrink: 0;
    background: var(--accent); border: 1px solid var(--accent); border-radius: var(--r);
    color: var(--accent-contrast-text, var(--bg)); cursor: pointer;
  }
  .new-btn:hover { opacity: 0.8; }

  .list-meta {
    display: flex; align-items: center; gap: 6px;
    padding: 5px 12px;
    font-size: 10px; font-family: var(--font-mono); color: var(--text-muted);
    border-bottom: 1px solid var(--border-light); flex-shrink: 0;
  }
  .sep { color: var(--border); }

  .list-scroll { flex: 1; overflow-y: auto; overflow-x: hidden; }

  .tree-wrap { padding: 4px 0; }

  .empty-msg {
    padding: 32px 16px; text-align: center;
    color: var(--text-muted); font-size: 12px;
  }

  /* ── Tree rows ── */
  .tree-row {
    display: flex; align-items: center; gap: 5px;
    padding-right: 8px; height: 26px;
    cursor: pointer; user-select: none;
    border-radius: 3px; margin: 0 4px;
    transition: background var(--t-fast);
    min-width: 0;
  }
  .tree-row:hover { background: var(--hover); }
  .file-row.active { background: var(--elevated); }

  .chevron {
    color: var(--text-muted); display: flex; align-items: center;
    flex-shrink: 0; transition: transform var(--t-fast);
  }
  .chevron.open { transform: rotate(90deg); }

  .t-icon { display: flex; align-items: center; justify-content: center; flex-shrink: 0; width: 16px; height: 16px; }
  .file-icon { opacity: 0.9; }

  .t-name {
    font-size: 12px; font-family: var(--font-sans);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    flex: 1; min-width: 0; color: var(--text-secondary);
  }
  .file-row.active .t-name { color: var(--text-primary); }

  .t-count {
    font-size: 10px; font-family: var(--font-mono);
    color: var(--text-muted); flex-shrink: 0;
  }

  /* ── Resize handle ── */
  /* Moved to app.css for global consistency */

  .editor-panel {
    display: flex; flex-direction: column;
    height: 100%; overflow: hidden;
    background: var(--bg); min-width: 0;
  }
  
  /* ── Empty Dashboard ── */
  .empty-dashboard {
    display: flex; flex-direction: column;
    align-items: center; justify-content: start;
    height: 100%; gap: 30px; padding: 60px 40px;
    background: var(--bg); color: var(--text-primary);
    overflow-y: auto;
  }
  .dash-search-container {
    width: 100%; max-width: 850px;
  }
  .dash-search {
    display: flex; align-items: center; gap: 8px;
    padding: 12px 18px; border-radius: var(--r);
    background: var(--surface); border: 1px solid var(--border);
    transition: all var(--t-fast);
  }
  .dash-search:focus-within { border-color: var(--xp); transform: translateY(-1px); }
  .dash-search input {
    border: none; background: transparent; outline: none;
    color: var(--text-primary); font-family: var(--font-sans); font-size: 14px; flex: 1;
  }

  .dash-widgets {
    display: grid; grid-template-columns: 1fr 1.2fr; gap: 24px;
    width: 100%; max-width: 850px;
  }
  .dash-widget {
    background: var(--surface); border: 1px solid var(--border-light); border-radius: var(--r);
    padding: 24px; display: flex; flex-direction: column; gap: 18px;
    min-width: 0;
  }
  .quick-note-widget { min-width: 0; overflow: hidden; }
  .dash-action-buttons {
    display: flex; flex-direction: column; gap: 10px;
  }
  .dash-btn {
    display: flex; align-items: center; gap: 10px;
    padding: 0 20px; border-radius: var(--r);
    background: var(--surface); border: 1px solid var(--border);
    color: var(--text-primary); cursor: pointer;
    font-size: 13px; font-family: var(--font-sans);
    transition: all var(--t-fast);
    height: 42px;
  }
  .primary-dash-btn {
    background: var(--xp); border-color: var(--xp); color: var(--xp-contrast-text, var(--bg)); font-weight: 600;
  }
  .primary-dash-btn:hover { background: var(--xp-2); border-color: var(--xp-2); transform: translateY(-1px); }

  .secondary-dash-btn {
    background: color-mix(in srgb, var(--xp-2) 16%, transparent);
    border-color: color-mix(in srgb, var(--xp-2) 45%, transparent);
    color: var(--text-primary);
  }
  .secondary-dash-btn:hover { background: color-mix(in srgb, var(--xp-2) 28%, transparent); border-color: var(--xp-2); }
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
    height: 1px; background: var(--border-light); margin: 5px 0;
  }

  .recent-list {
    display: flex; flex-direction: column; gap: 8px;
  }
  .recent-item {
    display: flex; align-items: center; gap: 10px; padding: 8px 12px;
    background: var(--bg); border: 1px solid var(--border-light); border-radius: 6px;
    cursor: pointer; transition: all var(--t-fast); text-align: left;
    min-width: 0; width: 100%;
  }
  .recent-item:hover { border-color: var(--border); background: var(--surface); }
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
    from { transform: translateX(0); }
    to { transform: translateX(calc(var(--scroll-distance, 0px) * -1)); }
  }
  .recent-time { font-size: 10px; color: var(--text-disabled); font-family: var(--font-mono); }


  /* ── Scientific Calculator (Joidy Styled) ── */
  .scientific-calc { 
    gap: 12px; 
    background: var(--surface);
    border: 1px solid var(--border);
    min-width: 0; /* Strict containment */
    overflow: hidden;
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  .calc-display {
    background: var(--bg); border: 1px solid var(--border); border-radius: var(--r);
    padding: 12px; display: flex; flex-direction: column; align-items: flex-end;
    min-width: 0; width: 100%;
    overflow: hidden;
  }
  .calc-history { color: var(--text-disabled); cursor: pointer; align-self: flex-start; margin-bottom: -15px; }
  .calc-input {
    width: 100%; border: none; color: var(--text-secondary); background: transparent;
    font-size: 13px; text-align: right; outline: none; margin-bottom: 2px;
    font-family: var(--font-mono);
  }
  .calc-res {
    font-size: 32px; color: var(--accent); font-weight: 600; font-family: var(--font-mono);
    min-height: 40px;
    width: 100%;
    text-align: right;
    white-space: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
  }
  /* Hide scrollbar for cleaner look */
  .calc-res::-webkit-scrollbar { display: none; }
  .calc-grid {
    display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px;
    flex: 1; /* Grow to fill space */
    grid-auto-rows: 1fr; /* All rows equal height */
  }
  .calc-btn {
    height: 100%; width: 100%; border: 1px solid var(--border-light); border-radius: 4px;
    background: var(--elevated); color: var(--text-secondary); cursor: pointer;
    font-size: 11px; transition: all var(--t-fast);
    display: flex; align-items: center; justify-content: center;
    font-family: var(--font-mono);
  }
  .calc-btn:hover { background: var(--border-light); color: var(--text-primary); border-color: var(--border); }
  .calc-btn.sm { color: var(--text-muted); font-size: 10px; }
  .calc-btn.num { color: var(--text-primary); font-weight: 500; font-size: 13px; }
  .calc-btn.op { background: color-mix(in srgb, var(--xp-2) 16%, transparent); color: var(--xp-2); font-size: 14px; }
  .calc-btn.clear { background: var(--xp); color: var(--xp-contrast-text, var(--bg)); font-weight: 600; border-color: var(--xp); }
  .calc-btn.equals { background: var(--xp-3); color: var(--xp-contrast-text, var(--bg)); font-weight: 600; font-size: 14px; border-color: var(--xp-3); }
  .calc-btn.equals:hover { opacity: 0.8; transform: translateY(-1px); }
  .calc-btn:active { transform: scale(0.95); }

  .scratchpad {
    width: 100%; height: 100px; resize: none; background: var(--bg);
    border: 1px solid var(--border-light); border-radius: 4px; padding: 10px;
    color: var(--text-primary); font-family: var(--font-sans); font-size: 13px;
    outline: none; transition: border-color var(--t-fast);
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
    position: fixed; top: 50px; bottom: 50px; left: 0; right: 0;
    z-index: 200;
    background: rgba(0,0,0,0.6); backdrop-filter: blur(2px);
    display: flex; align-items: center; justify-content: center;
  }
  .folder-modal {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 20px;
    display: flex; flex-direction: column; gap: 14px;
    width: 100%;
    height: 100%;
    max-width: 800px;
    min-height: 0;
  }
  .folder-modal-title {
    font-size: 14px; font-weight: 600; color: var(--text-primary);
    margin: 0;
  }
  .folder-label {
    font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;
  }
  .folder-color-row {
    display: flex; align-items: center; gap: 8px; width: 100%;
  }
  .folder-color-input {
    flex: 1; height: 28px; border: 1px solid var(--border);
    border-radius: 4px; cursor: pointer; padding: 0; background: none;
  }
  .folder-color-input::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  .folder-color-input::-webkit-color-swatch {
    border: none; border-radius: 3px;
  }
  .folder-hex-input {
    width: 75px; padding: 6px 8px; border: 1px solid var(--border);
    border-radius: 4px; background: var(--bg); color: var(--text-primary);
    font-size: 11px; text-align: center;
    text-transform: uppercase;
  }
  .folder-icon-row {
    display: flex; flex-direction: column; gap: 8px;
    flex: 1;
    min-height: 0;
  }
  .folder-icon-header {
    display: flex; flex-direction: column; gap: 8px;
  }
  .folder-search-row {
    display: flex; align-items: center; gap: 6px;
    padding: 6px 10px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px;
  }
  .folder-search-input {
    background: transparent; border: none; outline: none;
    font-size: 12px; color: var(--text-primary); width: 100%;
  }
  .folder-search-input::placeholder { color: var(--text-muted); }
  .no-icons-msg {
    grid-column: 1 / -1; text-align: center; color: var(--text-muted);
    font-size: 12px; padding: 20px;
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
    width: 40px; height: 40px;
    display: flex; align-items: center; justify-content: center;
    border: 1px solid var(--border-light); border-radius: 6px; background: var(--bg);
    color: var(--text-muted); cursor: pointer; transition: all var(--t-fast);
  }
  .folder-icon-btn:hover {
    border-color: var(--border); color: var(--text-primary);
  }
  .folder-icon-btn.selected {
    border-color: var(--xp); color: var(--xp); background: color-mix(in srgb, var(--xp) 12%, transparent);
  }
  .folder-modal-btns {
    display: flex; gap: 8px; margin-top: 6px;
  }
  .folder-modal-btns button {
    flex: 1; padding: 8px; border-radius: 5px; font-size: 12px;
    cursor: pointer; border: 1px solid var(--border);
    background: var(--bg); color: var(--text-secondary);
  }
  .folder-modal-btns button:first-child:hover {
    border-color: var(--text-muted); color: var(--text-primary);
  }
  .folder-modal-btns button:last-child {
    background: var(--xp); border-color: var(--xp);
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
    background: var(--error, #ef4444);
    border-color: var(--error, #ef4444);
    color: #fff;
  }
  .delete-confirm-actions .btn-danger:hover {
    opacity: 0.85;
  }
</style>
