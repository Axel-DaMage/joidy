<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { Search, Plus, X, List, FolderTree, ChevronRight, FileEdit, FolderPlus, ChevronsUpDown, ArrowUpDown } from 'lucide-svelte';
  import DynamicIcon from '$lib/components/DynamicIcon.svelte';
  import NoteEditor from '$lib/components/NoteEditor.svelte';
  import NoteCard from '$lib/components/NoteCard.svelte';
  import { notes, notesLoading, loadNotes, createNote, updateNote, deleteNote, aiSuggestions } from '$lib/stores/notes';
  import { buildTree, flattenTree, type SortMode } from '$lib/utils/fileTree';
  import { showHiddenFiles, showTrash } from '$lib/stores/settings';
  import type { Note } from '$lib/api';

  // ── State ────────────────────────────────────────────────────────────────────
  let search = '';
  let selectedNote: Note | null = null;
  let showEditor = false;
  let editingNew = false;
  let viewMode: 'tree' | 'list' = 'tree';

  // ── Explorer toolbar state ───────────────────────────────────────────────────
  let sortMode: SortMode = 'edit-new';
  let showSortMenu = false;
  let allCollapsed = false;

  function handleCreateFolder() {
    alert('Próximamente: Las carpetas están enlazadas a la raíz de tu sistema de archivos.');
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
  }

  // Resizable panel
  const MIN_W = 160;
  const MAX_W = 520;
  let panelWidth = 260;
  let dragging = false;

  // Tree collapse state — Set of collapsed folder paths
  let collapsed = new Set<string>();

  $: showNew = $page.url.searchParams.get('new') === '1';
  $: selectedId = $page.url.searchParams.get('id');

  // Flat filtered list for list mode
  $: filtered = $notes.filter(n =>
    !search ||
    n.title.toLowerCase().includes(search.toLowerCase()) ||
    n.tags.some(t => t.includes(search.toLowerCase()))
  );

  // Tree → flat list (no recursive component, avoids Svelte 5 HMR issues)
  $: tree = buildTree($notes, viewMode === 'tree' ? search : '', $showTrash, $showHiddenFiles, sortMode);
  $: flatNodes = flattenTree(tree, collapsed);

  onMount(async () => {
    const saved = localStorage.getItem('notes-panel-w');
    if (saved) panelWidth = Math.max(MIN_W, Math.min(MAX_W, parseInt(saved)));
    await loadNotes();
    if (showNew) openNew();
    if (selectedId) {
      const n = $notes.find(n => String(n.id) === selectedId);
      if (n) openNote(n);
    }
  });

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
      localStorage.setItem('notes-panel-w', String(panelWidth));
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
  }

  // ── Note actions ─────────────────────────────────────────────────────────────
  function openNote(note: Note) {
    selectedNote = note;
    showEditor = true;
    editingNew = false;
    aiSuggestions.set([]);
  }

  function openNew() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = false;
    aiSuggestions.set([]);
  }

  function openMomentary() {
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = true;
  }

  function openDaily() {
    const today = new Date().toISOString().split('T')[0];
    selectedNote = null;
    showEditor = true;
    editingNew = true;
    isMomentary = false; // Usually daily notes are real
    // We would pre-fill title here if NoteEditor allowed it easily via props
  }

  function closeEditor() {
    showEditor = false;
    selectedNote = null;
    goto('/notes');
  }

  async function handleSave(e: CustomEvent<{ title: string; content: string; tags: string[] }>) {
    const { title, content, tags } = e.detail;
    if (isMomentary) {
      momentaryDraft = { title, content, tags };
      return; 
    }
    if (editingNew) {
      const n = await createNote(title, content, tags);
      if (n) { selectedNote = n; editingNew = false; }
    } else if (selectedNote) {
      await updateNote(selectedNote.id, { title, content, tags });
    }
  }

  async function handleDelete() {
    if (selectedNote) {
      await deleteNote(selectedNote.id);
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

<svelte:window on:click={() => { if (showSortMenu) showSortMenu = false; }} />

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
              <button class="sort-btn" class:active={sortMode==='az'} on:click={() => {sortMode='az'; showSortMenu=false}}>Ordenar por nombre (A-Z)</button>
              <button class="sort-btn" class:active={sortMode==='za'} on:click={() => {sortMode='za'; showSortMenu=false}}>Ordenar por nombre (Z-A)</button>
              <div class="sort-divider"></div>
              <button class="sort-btn" class:active={sortMode==='edit-new'} on:click={() => {sortMode='edit-new'; showSortMenu=false}}>Editar (más reciente) {#if sortMode==='edit-new'}✓{/if}</button>
              <button class="sort-btn" class:active={sortMode==='edit-old'} on:click={() => {sortMode='edit-old'; showSortMenu=false}}>Editar (más antiguo) {#if sortMode==='edit-old'}✓{/if}</button>
              <div class="sort-divider"></div>
              <button class="sort-btn" class:active={sortMode==='create-new'} on:click={() => {sortMode='create-new'; showSortMenu=false}}>Creado (nuevo-antiguo) {#if sortMode==='create-new'}✓{/if}</button>
              <button class="sort-btn" class:active={sortMode==='create-old'} on:click={() => {sortMode='create-old'; showSortMenu=false}}>Creado (antiguo-nuevo) {#if sortMode==='create-old'}✓{/if}</button>
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

    <div class="list-scroll">
      {#if $notesLoading}
        <div class="empty-msg">Cargando...</div>

      {:else if viewMode === 'tree'}
        {#if flatNodes.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else}
          <div class="tree-wrap">
            {#each flatNodes as node (node.path)}
              {#if node.type === 'folder'}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row folder-row"
                  style="padding-left: {8 + node.depth * 14}px"
                  on:click={() => toggleFolder(node.path)}
                >
                  <span class="chevron" class:open={!collapsed.has(node.path)}>
                    <ChevronRight size={11} />
                  </span>
                  <div class="t-icon"><DynamicIcon name={node.icon} size={13} color={node.color} pack={node.pack} /></div>
                  <span class="t-name folder-name">{node.name}</span>
                  <span class="t-count">{node.childCount}</span>
                </div>
              {:else}
                <!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
                <div
                  class="tree-row file-row"
                  class:active={node.note?.id === selectedNote?.id}
                  style="padding-left: {20 + node.depth * 14}px"
                  on:click={() => node.note && openNote(node.note)}
                >
                  <div class="t-icon file-icon"><DynamicIcon name={node.icon} size={11} color={node.color} pack={node.pack} /></div>
                  <span class="t-name file-name">{node.name}</span>
                </div>
              {/if}
            {/each}
          </div>
        {/if}

      {:else}
        {#if filtered.length === 0}
          <div class="empty-msg">{search ? 'Sin resultados.' : 'Sin notas.'}</div>
        {:else}
          {#each filtered as note}
            <NoteCard {note} active={selectedNote?.id === note.id} on:select={(e) => openNote(e.detail)} />
          {/each}
        {/if}
      {/if}
    </div>
  </aside>

  <!-- ── Resize handle ─────────────────────────────────────────────────────── -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div class="resize-handle" on:mousedown={startResize}></div>

  <!-- ── Editor panel ──────────────────────────────────────────────────────── -->
  <div class="editor-panel">
    {#if showEditor}
      {#key editingNew ? (isMomentary ? 'momentary' : 'new') : selectedNote?.id}
        <NoteEditor
          note={editingNew ? (isMomentary ? { ...momentaryDraft, id: -1, source: 'momentary' } as any : null) : selectedNote}
          momentary={isMomentary}
          on:save={handleSave}
          on:cancel={closeEditor}
          on:delete={handleDelete}
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
              <button class="dash-btn secondary-dash-btn" on:click={openDaily}>
                <DynamicIcon name="Calendar" size={16} /> Nota Diaria
              </button>
              <button class="dash-btn secondary-dash-btn momentary-btn" on:click={openMomentary}>
                <Plus size={16} /> Nota Momentánea
              </button>
            </div>
            
            <div class="dash-divider"></div>
            <div class="dash-widget-title"><DynamicIcon name="History" size={13}/> Recientes</div>
            <div class="recent-list">
              {#each $notes.slice(0, 3) as note}
                <button class="recent-item" on:click={() => openNote(note)}>
                  <DynamicIcon name="File" size={12} color="var(--text-disabled)" />
                  <span class="recent-name">{note.title}</span>
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
    background: var(--accent); border: none; border-radius: var(--r);
    color: var(--bg); cursor: pointer; transition: opacity var(--t-fast);
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
  .resize-handle {
    background: var(--border-light); cursor: col-resize;
    transition: background var(--t-fast); position: relative; z-index: 1;
  }
  .resize-handle:hover,
  .notes-page.dragging .resize-handle { background: var(--text-muted); }
  .resize-handle::after {
    content: ''; position: absolute; inset: 0 -4px;
  }

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
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  }
  .dash-search:focus-within { border-color: var(--accent); transform: translateY(-1px); }
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
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
  }
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
    background: var(--accent); border: none; color: var(--bg); font-weight: 600;
  }
  .primary-dash-btn:hover { background: var(--accent); opacity: 0.9; transform: translateY(-1px); }
  
  .secondary-dash-btn:hover { background: var(--elevated); border-color: var(--accent); color: var(--accent); }

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
  }
  .recent-item:hover { border-color: var(--accent); background: var(--surface); }
  .recent-name { flex: 1; font-size: 12px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
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
  .calc-btn:hover { background: var(--border-light); color: var(--text-primary); border-color: var(--accent); }
  .calc-btn.sm { color: var(--text-muted); font-size: 10px; }
  .calc-btn.num { color: var(--text-primary); font-weight: 500; font-size: 13px; }
  .calc-btn.op { background: rgba(var(--accent-rgb), 0.05); color: var(--accent); font-size: 14px; }
  .calc-btn.clear { background: var(--accent); color: var(--bg); font-weight: 600; border: none; }
  .calc-btn.equals { background: var(--accent); color: var(--bg); font-weight: 600; font-size: 14px; border: none; }
  .calc-btn.equals:hover { opacity: 0.8; transform: translateY(-1px); }
  .calc-btn:active { transform: scale(0.95); }

  .scratchpad {
    width: 100%; height: 100px; resize: none; background: var(--bg);
    border: 1px solid var(--border-light); border-radius: 4px; padding: 10px;
    color: var(--text-primary); font-family: var(--font-sans); font-size: 13px;
    outline: none; transition: border-color var(--t-fast);
  }
  .momentary-btn {
    border-style: dashed;
    color: var(--text-muted);
  }
  .momentary-btn:hover {
    color: var(--accent);
    border-style: solid;
  }
</style>
