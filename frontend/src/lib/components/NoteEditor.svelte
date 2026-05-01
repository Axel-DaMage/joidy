<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { Eye, EyeOff, Save, Trash2, X, Palette, Search, Maximize, ChevronLeft, ChevronRight } from 'lucide-svelte';
  import * as L from 'lucide-svelte';
  import DynamicIcon from './DynamicIcon.svelte';
  import { marked } from 'marked';
  import TagChip from './TagChip.svelte';
  import { aiSuggestions, fetchAISuggestions, findNoteByTitle } from '$lib/stores/notes';
  import { activeIconPack, showFrontmatter, hideTagsLine } from '$lib/stores/settings';
  import { api, type Note } from '$lib/api';
  import { goto } from '$app/navigation';

  // Configure marked once — GFM enables tables, strikethrough, autolinks
  marked.use({ gfm: true, breaks: true });

  export let note: Note | null = null;
  export let momentary = false;
  export let hasPrev = false;
  export let hasNext = false;

  function extractTagsFromContent(text: string): string[] {
    const extracted = new Set<string>();
    
    // Match line like: # Tags: [[tag1]] [[tag2]]
    const lineRegex = /^#\s*Tags?:\s*(.*)$/gim;
    let lineMatch;
    while ((lineMatch = lineRegex.exec(text)) !== null) {
      const lineTags = lineMatch[1];
      const tagRegex = /\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g;
      let tagMatch;
      while ((tagMatch = tagRegex.exec(lineTags)) !== null) {
        extracted.add(tagMatch[1].trim().toLowerCase());
      }
    }
    
    // Match individual #Tag: [[tag]]
    const regex = /#Tag:\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/gi;
    let match;
    while ((match = regex.exec(text)) !== null) {
      extracted.add(match[1].trim().toLowerCase());
    }
    
    return Array.from(extracted);
  }

  function escapeRegExp(string: string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  let title = note?.title ?? '';
  let content = note?.content ?? '';
  let tags: string[] = note?.tags ?? [];
  let previousContentTags = extractTagsFromContent(content);
  for (const t of previousContentTags) {
    if (!tags.includes(t)) tags.push(t);
  }
  let tagInput = '';
  let saving = false;
  let saved = false;
  let previewMode = false;
  let aiTimeout: ReturnType<typeof setTimeout>;
  
  let showIconSettings = false;
  let customColor = '#ffffff';
  let iconSearchTerm = '';
  const ALL_ICONS = Object.keys(L).filter(k => /^[A-Z]/.test(k) && k !== 'default' && k !== 'createLucideIcon');
  
  let visibleLimit = 150;

  $: filteredIconsAll = ALL_ICONS.filter(ic => ic.toLowerCase().includes(iconSearchTerm.toLowerCase()));
  $: filteredIcons = filteredIconsAll.slice(0, visibleLimit);

  // Reset limit when search term changes
  $: if (iconSearchTerm !== undefined) {
    visibleLimit = 150;
  }

  function handleIconScroll(e: Event) {
    const target = e.currentTarget as HTMLElement;
    if (target.scrollHeight - target.scrollTop - target.clientHeight < 120) {
      if (visibleLimit < filteredIconsAll.length) {
        visibleLimit += 150;
      }
    }
  }

  let backlinks: Note[] = [];

  // Fetch backlinks on mount or when note changes
  $: if (note) {
    api.notes.backlinks(note.id).then(res => backlinks = res).catch(() => backlinks = []);
  }

  const dispatch = createEventDispatcher<{
    save: { title: string; content: string; tags: string[] };
    cancel: void;
    delete: void;
    click: string;
    prev: void;
    next: void;
  }>();

  // Markdown → HTML via marked (handles tables, blockquotes, lists, etc.)
  function renderMarkdown(md: string): string {
    if (!md.trim()) return '<p style="color:var(--text-muted);font-style:italic;">Escribe algo para ver el preview...</p>';

    // Hide tags line from preview if requested
    let preprocessed = md;
    if ($hideTagsLine && tags.length > 0) {
      preprocessed = preprocessed.replace(/^#\s*Tags?:\s*.*$/gim, '');
    }

    // Pre-process Obsidian wikilinks → HTML spans before marked runs
    // (marked doesn't know about [[links]] and would render them as plain text)
    preprocessed = preprocessed.replace(/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g, (match, title, alias) => {
      const display = alias || title;
      return `<span class="wikilink" data-title="${title.trim()}">${display}</span>`;
    });

    return String(marked.parse(preprocessed));
  }

  function handlePreviewClick(e: MouseEvent) {
    const target = e.target as HTMLElement;
    if (target.classList.contains('wikilink')) {
      const title = target.getAttribute('data-title');
      if (title) {
        const linkedNote = findNoteByTitle(title);
        if (linkedNote) {
          goto(`/notes?id=${linkedNote.id}`);
        } else {
          // Future: Option to create missing note
          console.log('Note not found:', title);
        }
      }
    }
  }

  $: rawFrontmatterMatch = content.match(/^---\n[\s\S]*?\n---/);
  $: rawFrontmatter = rawFrontmatterMatch ? rawFrontmatterMatch[0] : '';

  $: tagsLineMatch = content.match(/^#\s*Tags?:\s*.*$/im);
  $: currentTagsLine = tagsLineMatch ? tagsLineMatch[0] : '';

  $: visibleEditorContent = (() => {
    let val = content;
    if (!$showFrontmatter && rawFrontmatter) {
      val = val.replace(/^---\n[\s\S]*?\n---[\n]*/, '');
    }
    if ($hideTagsLine && tags.length > 0 && currentTagsLine) {
      val = val.replace(/^#\s*Tags?:\s*.*$/im, '').trim();
    }
    return val;
  })();

  $: wordCount = visibleEditorContent.trim() ? visibleEditorContent.trim().split(/\s+/).length : 0;
  $: charCount = visibleEditorContent.length;
  $: renderedHtml = renderMarkdown(visibleEditorContent);

  function updateVisibleContent(e: Event) {
    const val = (e.currentTarget as HTMLTextAreaElement).value;
    let nextContent = val;

    if ($hideTagsLine && tags.length > 0 && currentTagsLine) {
      if (!nextContent.includes(currentTagsLine)) {
        nextContent = nextContent.trim() + '\n\n' + currentTagsLine;
      }
    }

    if (!$showFrontmatter && rawFrontmatter) {
      nextContent = rawFrontmatter + '\n\n' + nextContent.trim();
    }
    
    content = nextContent;
    
    const currentContentTags = extractTagsFromContent(content);
    const added = currentContentTags.filter(t => !previousContentTags.includes(t));
    const removed = previousContentTags.filter(t => !currentContentTags.includes(t));
    
    let tagsChanged = false;
    let newTags = [...tags];
    
    for (const a of added) {
      if (!newTags.includes(a)) {
        newTags.push(a);
        tagsChanged = true;
      }
    }
    
    for (const r of removed) {
      if (newTags.includes(r)) {
        newTags = newTags.filter(x => x !== r);
        tagsChanged = true;
      }
    }
    
    if (tagsChanged) tags = newTags;
    previousContentTags = currentContentTags;

    onContentChange();
  }

  function addTag(t: string) {
    const clean = t.trim().toLowerCase();
    if (clean && !tags.includes(clean)) {
      tags = [...tags, clean];
      const currentContentTags = extractTagsFromContent(content);
      if (!currentContentTags.includes(clean)) {
        const tagsLineMatch = content.match(/^#\s*Tags?:\s*(.*)$/im);
        if (tagsLineMatch) {
          content = content.replace(/^#\s*Tags?:\s*(.*)$/im, `# Tags: $1 [[${clean}]]`);
        } else {
          const prefix = content.endsWith('\n') ? '' : '\n';
          content += `${prefix}\n# Tags: [[${clean}]]`;
        }
        previousContentTags.push(clean);
      }
    }
    tagInput = '';
  }

  function removeTag(t: string) {
    tags = tags.filter(x => x !== t);
    
    // Remove individual #Tag: [[t]]
    const regex1 = new RegExp(`\\n?\\s*#Tag:\\s*\\[\\[${escapeRegExp(t)}(?:\\|[^\\]]+)?\\]\\]`, 'gi');
    content = content.replace(regex1, '');
    
    // Remove from # Tags: [[...]] line
    const regex2 = new RegExp(`\\[\\[${escapeRegExp(t)}(?:\\|[^\\]]+)?\\]\\]\\s*`, 'gi');
    content = content.split('\n').map(line => {
      if (/^#\s*Tags?:\s*/i.test(line)) {
        let newLine = line.replace(regex2, '').trim();
        // if only "# Tags:" is left, remove the line
        if (/^#\s*Tags?:\s*$/i.test(newLine)) return '';
        return newLine;
      }
      return line;
    }).join('\n');
    
    previousContentTags = previousContentTags.filter(x => x !== t);
  }

  function onTagKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(tagInput); }
    else if (e.key === 'Backspace' && tagInput === '' && tags.length > 0) tags = tags.slice(0, -1);
  }

  function onContentChange() {
    if (!note || content.length < 20) return;
    clearTimeout(aiTimeout);
    aiTimeout = setTimeout(() => {
      if (note) fetchAISuggestions(note.id, content, tags);
    }, 2000);
  }

  function acceptSuggestion(tag: string) {
    addTag(tag);
    aiSuggestions.update(s => s.filter(x => x.tag !== tag));
  }

  function dismissSuggestion(tag: string) {
    aiSuggestions.update(s => s.filter(x => x.tag !== tag));
  }

  onDestroy(() => clearTimeout(aiTimeout));

  async function handleSave() {
    if (!title.trim()) return;
    saving = true;
    dispatch('save', { title: title.trim(), content, tags });
    saving = false;
    saved = true;
    setTimeout(() => (saved = false), 2000);
  }

  function pickIcon(ic: string) {
    updateFrontmatter('icon', ic);
    updateFrontmatter('iconPack', $activeIconPack);
  }

  function updateFrontmatter(key: string, value: string) {
    const m = content.match(/^---\n([\s\S]*?)\n---/);
    if (m) {
      let yaml = m[1];
      const regex = new RegExp(`(?:^|\\n)${key}:.*`);
      if (regex.test(yaml)) {
        yaml = yaml.replace(regex, `\n${key}: ${value}`);
      } else {
        yaml += `\n${key}: ${value}`;
      }
      yaml = yaml.replace(/\n{2,}/g, '\n').trim();
      content = content.replace(/^---\n[\s\S]*?\n---/, `---\n${yaml}\n---`);
    } else {
      content = `---\n${key}: ${value}\n---\n\n` + content;
    }
    onContentChange();
    handleSave();
  }

  function onKeydown(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
      e.preventDefault();
      previewMode = !previewMode;
    }
    if (e.key === 'Escape' && zenMode) {
      e.preventDefault();
      e.stopPropagation();
      zenMode = false;
    }
    if (e.altKey && e.key === 'ArrowLeft' && hasPrev) {
      e.preventDefault();
      dispatch('prev');
    }
    if (e.altKey && e.key === 'ArrowRight' && hasNext) {
      e.preventDefault();
      dispatch('next');
    }
  }

  let zenMode = false;
  let backdropEl: HTMLElement;
  let textareaEl: HTMLTextAreaElement;

  function syncScroll() {
    if (backdropEl && textareaEl) {
      backdropEl.scrollTop = textareaEl.scrollTop;
      backdropEl.scrollLeft = textareaEl.scrollLeft;
    }
  }

  function highlightMarkdown(text: string): string {
    if (!text) return '';
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    
    // Multiline code blocks
    html = html.replace(/^(`{3,})(.*)$/gm, '<span style="color: var(--text-muted);">$1$2</span>');
    
    // Headers
    html = html.replace(/^(#{1,6})(\s+.+)$/gm, (match, hashes, rest) => {
      const level = hashes.length;
      return `<span style="color: var(--md-h${level}); font-weight: 500;">${hashes}${rest}</span>`;
    });

    // Blockquotes
    html = html.replace(/^(&gt;\s*)(.*)$/gm, '<span style="color: var(--text-secondary); border-left: 2px solid var(--border); padding-left: 6px; font-style: italic;">$1$2</span>');
    
    // Lists (unordered and ordered)
    html = html.replace(/^(\s*)([-*+]|\d+\.)(\s+)/gm, '$1<span style="color: var(--md-h1, var(--xp)); font-weight: bold;">$2</span>$3');

    // Bold + Italic
    html = html.replace(/(\*\*\*|___)([^\s](?:.*?[^\s])?)\1/g, '<span style="font-weight: bold; font-style: italic; color: var(--md-h2, var(--xp));">$1$2$1</span>');

    // Bold
    html = html.replace(/(\*\*|__)([^\s](?:.*?[^\s])?)\1/g, '<span style="font-weight: bold; color: var(--text-primary);">$1$2$1</span>');
    
    // Italic (using negative lookbehinds/lookaheads to prevent matching bold borders)
    html = html.replace(/(?<!\*)\*([^\s\*](?:.*?[^\s\*])?)\*(?!\*)/g, '<span style="font-style: italic; color: var(--text-secondary);">*$1*</span>');
    html = html.replace(/(?<!_)_([^\s_](?:.*?[^\s_])?)_(?!_)/g, '<span style="font-style: italic; color: var(--text-secondary);">_$1_</span>');
    
    // Strikethrough
    html = html.replace(/(~~)([^\s](?:.*?[^\s])?)\1/g, '<span style="text-decoration: line-through; opacity: 0.6;">$1$2$1</span>');
    
    // Inline code
    html = html.replace(/(`)(.*?)\1/g, '<span style="background: var(--elevated); color: var(--md-h1, var(--xp)); border-radius: 3px; padding: 0 2px;">$1$2$1</span>');
    
    // Links (standard markdown)
    html = html.replace(/(\[)([^\]]+)(\])(\()([^\)]+)(\))/g, '<span style="color: var(--text-muted)">$1</span><span style="color: var(--md-h2, var(--xp))">$2</span><span style="color: var(--text-muted)">$3$4</span><span style="color: var(--text-muted); text-decoration: underline;">$5</span><span style="color: var(--text-muted)">$6</span>');

    // Tags line
    html = html.replace(/^(#\s*Tags?:\s*)(.*)$/gim, '<span style="opacity: 0.3; font-size: 0.9em;">$1$2</span>');

    // Obsidian Wikilinks & Tags
    html = html.replace(/(#Tag:\s*)?(\[\[)([^\]]+)(\]\])/g, (match, tagPrefix, openBracket, content, closeBracket) => {
      if (tagPrefix) {
         return `<span style="opacity: 0.3; font-size: 0.9em;">${tagPrefix}${openBracket}${content}${closeBracket}</span>`;
      }
      return `<span style="color: var(--text-muted)">${openBracket}</span><span style="color: var(--md-h2, var(--xp))">${content}</span><span style="color: var(--text-muted)">${closeBracket}</span>`;
    });
    
    // Ensure trailing newlines render correctly
    if (html.endsWith('\n')) {
      html += '<br/>';
    }
    
    return html;
  }

  $: editorHighlightedHtml = highlightMarkdown(visibleEditorContent);
</script>

<svelte:window on:keydown={onKeydown} />

<div class="editor-shell" class:zen-mode={zenMode}>
  <!-- Toolbar -->
  {#if !zenMode}
  <div class="toolbar">
    <div class="toolbar-left">
      {#if !momentary && note}
      <div class="nav-controls toolbar-nav">
        <button class="toolbar-btn icon-only" disabled={!hasPrev} on:click={() => dispatch('prev')} title="Nota anterior (Alt + ←)">
          <ChevronLeft size={14} />
        </button>
        <button class="toolbar-btn icon-only" disabled={!hasNext} on:click={() => dispatch('next')} title="Siguiente nota (Alt + →)">
          <ChevronRight size={14} />
        </button>
      </div>
      {/if}
    </div>

    <div class="toolbar-right">
      <span class="stat">{wordCount} palabras</span>
      <span class="stat">{charCount} caracteres</span>

      <button
        class="toolbar-btn icon-only"
        class:active={zenMode}
        on:click={() => zenMode = !zenMode}
        title="Modo Zen (Esc para salir)"
      >
        <Maximize size={14} />
      </button>

      <div class="icon-flyout-container">
        <button
          class="toolbar-btn"
          class:active={showIconSettings}
          on:click={() => showIconSettings = !showIconSettings}
          title="Personalizar Icono"
        >
          <Palette size={14} />
        </button>
        {#if showIconSettings}
          <div class="icon-flyout">
            <div class="flyout-header">
              <Search size={12} color="var(--text-muted)" />
              <input class="icon-search-input" bind:value={iconSearchTerm} placeholder="Buscar icono..." />
            </div>
            <div class="icon-grid" on:scroll={handleIconScroll}>
              {#each filteredIcons as ic}
                <button class="icon-grid-btn" on:click={() => pickIcon(ic)} title={ic}>
                  <DynamicIcon name={ic} size={16} />
                </button>
              {/each}
              {#if filteredIcons.length === 0}
                <span class="no-icons-msg">No se encontraron iconos</span>
              {/if}
            </div>
            <div class="color-picker-row">
              <label for="icon-color">Color:</label>
              <input type="color" id="icon-color" bind:value={customColor} on:change={(e) => updateFrontmatter('iconColor', e.currentTarget.value)} />
              <button class="clear-btn" on:click={() => { updateFrontmatter('iconColor', ''); updateFrontmatter('icon', ''); updateFrontmatter('iconPack', ''); }}>Reset</button>
            </div>
          </div>
        {/if}
      </div>

      <button
        class="toolbar-btn"
        class:active={previewMode}
        on:click={() => previewMode = !previewMode}
        title="Alternar preview (Ctrl+P)"
      >
        {#if previewMode}<EyeOff size={14} />{:else}<Eye size={14} />{/if}
        <span>{previewMode ? 'Editor' : 'Preview'}</span>
      </button>

      <button
        class="toolbar-btn save-btn"
        class:saved
        on:click={handleSave}
        disabled={saving || !title.trim()}
        title="Guardar (Ctrl+S)"
      >
        <Save size={14} />
        <span class="save-status">{saved ? 'Guardado' : saving ? '...' : note ? 'Guardar' : 'Crear'}</span>
      </button>

      {#if note}
        <button class="toolbar-btn danger-btn" on:click={() => dispatch('delete')} title="Eliminar nota">
          <Trash2 size={14} />
        </button>
      {/if}

      <button class="toolbar-btn" on:click={() => dispatch('cancel')} title="Cerrar">
        <X size={14} />
      </button>
    </div>
  </div>
  {/if}

  <!-- Title -->
  <div class="title-row">
    <input
      class="title-input"
      bind:value={title}
      placeholder="Título de la nota..."
      on:keydown={(e) => e.key === 'Enter' && handleSave()}
    />
  </div>

  <!-- Tags bar -->
  <div class="tags-bar">
    {#each tags as tag}
      <TagChip {tag} removable on:remove={(e) => removeTag(e.detail)} on:click={(e) => {
        const linkedNote = findNoteByTitle(e.detail);
        if (linkedNote) {
          goto(`/notes?id=${linkedNote.id}`);
        }
      }} />
    {/each}
    <input
      class="tag-input"
      bind:value={tagInput}
      on:keydown={onTagKeydown}
      placeholder="+ tag..."
    />
    {#if $aiSuggestions.length > 0}
      <span class="ai-label">ia:</span>
      {#each $aiSuggestions as s}
        <button class="suggestion-chip" on:click={() => acceptSuggestion(s.tag)}>
          {s.tag} <span class="conf">{Math.round(s.confidence * 100)}%</span>
        </button>
        <button class="dismiss-btn" on:click={() => dismissSuggestion(s.tag)}>×</button>
      {/each}
    {/if}
  </div>

  <!-- Content area -->
  <div class="content-area">
    {#if previewMode}
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div class="preview" on:dblclick={() => previewMode = false} on:click={handlePreviewClick}>
        {@html renderedHtml}

        {#if backlinks.length > 0}
          <div class="backlinks-section">
            <h5 class="mono">BACKLINKS</h5>
            <div class="backlinks-grid">
              {#each backlinks as bl}
                <button class="backlink-card" on:click={() => goto(`/notes?id=${bl.id}`)}>
                  <span class="bl-title">{bl.title}</span>
                  <span class="bl-meta mono">{bl.source === 'obsidian' ? '⬡' : '◆'}</span>
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {:else}
      <div class="editor-container">
        <div class="backdrop" bind:this={backdropEl} aria-hidden="true">
          <div class="highlights">{@html editorHighlightedHtml}</div>
        </div>
        <textarea
          class="content-textarea"
          bind:this={textareaEl}
          value={visibleEditorContent}
          on:input={updateVisibleContent}
          on:scroll={syncScroll}
          placeholder="Escribe en markdown... (Ctrl+S para guardar, Ctrl+P para preview)"
          spellcheck="false"
        ></textarea>
      </div>
    {/if}
  </div>
</div>

<style>
  .editor-shell {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: var(--surface);
  }

  .editor-shell.zen-mode {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 9999;
    border-left: none;
    background: var(--bg);
    padding-top: 40px;
  }

  /* ── Toolbar ── */
  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 20px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    gap: var(--s3);
    position: relative;
    z-index: 20;
  }

  .icon-flyout-container {
    position: relative;
    display: flex;
  }

  .icon-flyout {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 5px;
    width: 240px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 10px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    z-index: 50;
  }

  .flyout-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-light);
  }

  .icon-search-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 11px;
    font-family: var(--font-sans);
    color: var(--text-primary);
    width: 100%;
  }
  .icon-search-input::placeholder { color: var(--text-muted); }

  .icon-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 6px;
    margin-bottom: 10px;
    max-height: 165px;
    overflow-y: auto;
    padding-right: 4px;
  }
  
  /* Scrollbar styles for the icon grid */
  .icon-grid::-webkit-scrollbar { width: 4px; }
  .icon-grid::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

  .no-icons-msg {
    grid-column: 1 / -1;
    text-align: center;
    font-size: 11px;
    color: var(--text-muted);
    padding: 10px 0;
  }

  .icon-grid-btn {
    width: 100%;
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg);
    border: 1px solid var(--border-light);
    border-radius: 4px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .icon-grid-btn:hover {
    background: var(--elevated);
    border-color: var(--accent);
    color: var(--text-primary);
  }

  .color-picker-row {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 12px;
    color: var(--text-secondary);
    font-family: var(--font-sans);
  }

  .color-picker-row input[type="color"] {
    flex: 1;
    height: 24px;
    padding: 0;
    border: none;
    border-radius: 4px;
    background: transparent;
    cursor: pointer;
  }

  .clear-btn {
    font-size: 11px;
    padding: 3px 8px;
    background: transparent;
    border: 1px solid var(--error);
    border-radius: 3px;
    color: var(--error);
    cursor: pointer;
    font-family: var(--font-mono);
    transition: all var(--t-fast);
  }
  .clear-btn:hover { background: var(--error); color: var(--bg); }


  .toolbar-left {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: var(--s2);
  }

  .note-source {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    letter-spacing: 0.05em;
  }

  .stat {
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-muted);
  }

  .toolbar-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-secondary);
    font-size: 11px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .toolbar-btn:hover { background: var(--elevated); color: var(--text-primary); }
  .toolbar-btn.active { border-color: var(--text-secondary); color: var(--text-primary); }
  .toolbar-btn:disabled { opacity: 0.4; cursor: default; }

  .save-btn { border-color: var(--accent); color: var(--accent); }
  .save-btn:hover { background: var(--accent); color: var(--bg); }
  .save-btn.saved { background: var(--success); border-color: var(--success); color: var(--bg); }

  .save-status {
    display: inline-block;
    min-width: 58px;
    text-align: center;
  }

  .danger-btn { color: var(--error); border-color: transparent; }
  .danger-btn:hover { border-color: var(--error); background: transparent; }

  /* ── Title ── */
  .title-row {
    padding: 20px 24px 12px;
    border-bottom: 1px solid var(--border-light, var(--border));
    flex-shrink: 0;
  }

  .toolbar-nav {
    margin-bottom: 0 !important;
  }

  .nav-controls {
    display: flex;
    gap: 4px;
  }

  .title-input {
    width: 100%;
    background: transparent;
    border: none;
    outline: none;
    font-size: 22px;
    font-weight: 400;
    font-family: var(--font-sans);
    color: var(--text-primary);
    line-height: 1.3;
  }
  .title-input::placeholder { color: var(--text-muted); }

  /* ── Tags bar ── */
  .tags-bar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 5px;
    padding: 10px 24px;
    border-bottom: 1px solid var(--border);
    flex-shrink: 0;
    background: var(--surface);
    min-height: 38px;
  }

  .tag-input {
    background: transparent;
    border: none;
    outline: none;
    font-size: 11px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    min-width: 80px;
  }
  .tag-input::placeholder { color: var(--text-muted); }

  .ai-label {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--xp);
    margin-left: 6px;
    opacity: 0.8;
  }

  .suggestion-chip {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 2px 7px;
    border: 1px solid var(--xp);
    border-radius: 2px;
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--xp);
    background: transparent;
    cursor: pointer;
    opacity: 0.8;
    transition: opacity var(--t-fast);
  }
  .suggestion-chip:hover { opacity: 1; }
  .conf { font-size: 9px; opacity: 0.6; }

  .dismiss-btn {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    padding: 0;
    margin-left: -4px;
  }

  /* ── Content ── */
  .content-area {
    flex: 1;
    overflow: hidden;
    display: flex;
  }

  .editor-container {
    position: relative;
    flex: 1;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .backdrop {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    pointer-events: none;
    background: transparent;
  }

  .highlights {
    padding: 24px;
    font-family: var(--font-mono);
    font-size: 14px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-wrap: break-word;
    color: var(--text-primary);
    tab-size: 2;
  }

  .content-textarea {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    outline: none;
    resize: none;
    padding: 24px;
    font-size: 14px;
    font-family: var(--font-mono);
    line-height: 1.7;
    color: transparent;
    caret-color: var(--text-primary);
    white-space: pre-wrap;
    word-wrap: break-word;
    tab-size: 2;
    overflow-y: auto;
  }
  .content-textarea::placeholder { color: var(--text-muted); }

  /* Style selection to be visible over transparent text */
  .content-textarea::selection {
    background: color-mix(in srgb, var(--xp) 30%, transparent);
    color: transparent;
  }

  /* ── Preview ── */
  .preview {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.8;
    color: var(--text-primary);
  }

  .preview :global(h1) { font-size: 20px; font-weight: 500; margin: 0 0 12px; color: var(--md-h1, var(--text-primary)); }
  .preview :global(h2) { font-size: 16px; font-weight: 500; margin: 16px 0 8px; color: var(--md-h2, var(--text-primary)); border-bottom: 1px solid var(--border); padding-bottom: 4px; }
  .preview :global(h3) { font-size: 14px; font-weight: 500; margin: 12px 0 6px; color: var(--md-h3, var(--text-secondary)); }
  .preview :global(h4) { font-size: 13px; font-weight: 500; margin: 10px 0 4px; color: var(--md-h4, var(--text-secondary)); }
  .preview :global(h5) { font-size: 12px; font-weight: 600; margin: 8px 0 2px; color: var(--md-h5, var(--text-muted)); }
  .preview :global(h6) { font-size: 11px; font-weight: 700; margin: 8px 0 2px; color: var(--md-h6, var(--text-muted)); text-transform: uppercase; }
  .preview :global(code) { font-family: var(--font-mono); font-size: 12px; background: var(--elevated); padding: 1px 5px; border-radius: 2px; color: var(--md-h1, var(--xp)); }
  .preview :global(pre) { background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r); padding: 16px; overflow-x: auto; margin: 12px 0; }
  .preview :global(pre code) { background: none; padding: 0; color: var(--text-primary); }
  .preview :global(blockquote) { border-left: 2px solid var(--border); margin: 0; padding: 4px 12px; color: var(--text-secondary); font-style: italic; }
  .preview :global(li) { margin: 4px 0; padding-left: 12px; list-style: none; }
  .preview :global(li)::before { content: "—"; margin-right: 8px; color: var(--text-muted); }
  .preview :global(hr) { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
  .preview :global(strong) { font-weight: 600; }
  .preview :global(p) { margin: 0 0 12px; }
  .preview :global(.wikilink) { color: var(--xp); border-bottom: 1px solid color-mix(in srgb, var(--xp) 40%, transparent); cursor: pointer; transition: border-bottom-color var(--t-fast); }
  .preview :global(.wikilink:hover) { border-bottom-color: var(--xp); }

  .backlinks-section {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
  }
  .backlinks-section h5 { font-size: 10px; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.1em; }
  .backlinks-grid { display: flex; flex-wrap: wrap; gap: 8px; }
  .backlink-card {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 12px; background: var(--elevated); border: 1px solid var(--border);
    border-radius: var(--r); cursor: pointer; transition: all var(--t-fast);
  }
  .backlink-card:hover { border-color: var(--text-secondary); background: var(--hover); }
  .bl-title { font-size: 12px; color: var(--text-primary); }
  .bl-meta { font-size: 10px; color: var(--text-muted); }
  .preview :global(.task) { font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); margin: 4px 0; }
  .preview :global(.task.done) { color: var(--success); }

  /* ── Tables (GFM) ── */
  .preview :global(table) {
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 13px;
    font-family: var(--font-mono);
  }
  .preview :global(th) {
    text-align: left;
    padding: 6px 14px;
    border-bottom: 1px solid var(--text-muted);
    color: var(--text-secondary);
    font-weight: 400;
    font-size: 11px;
    letter-spacing: 0.04em;
    white-space: nowrap;
  }
  .preview :global(td) {
    padding: 5px 14px;
    border-bottom: 1px solid var(--border-light, var(--border));
    color: var(--text-primary);
    vertical-align: top;
  }
  .preview :global(tr:last-child td) { border-bottom: none; }
  .preview :global(tr:hover td) { background: var(--elevated); }

  /* ── Task lists (marked renders - [x] as <input type="checkbox">) ── */
  .preview :global(input[type="checkbox"]) {
    appearance: none;
    width: 12px;
    height: 12px;
    border: 1px solid var(--text-muted);
    border-radius: 2px;
    margin-right: 6px;
    vertical-align: middle;
    position: relative;
    flex-shrink: 0;
  }
  .preview :global(input[type="checkbox"]:checked) {
    background: var(--success);
    border-color: var(--success);
  }
  .preview :global(input[type="checkbox"]:checked::after) {
    content: '✓';
    position: absolute;
    top: -2px;
    left: 1px;
    font-size: 9px;
    color: var(--bg);
  }
  .preview :global(.task-list-item) { list-style: none; padding-left: 0; }
  .preview :global(.task-list-item)::before { content: none; }

  /* ── Strikethrough (GFM) ── */
  .preview :global(del) { text-decoration: line-through; color: var(--text-muted); }

  /* ── Links ── */
  .preview :global(a) { color: var(--xp); text-decoration: none; border-bottom: 1px solid color-mix(in srgb, var(--xp) 35%, transparent); }
  .preview :global(a:hover) { border-bottom-color: var(--xp); }
</style>
