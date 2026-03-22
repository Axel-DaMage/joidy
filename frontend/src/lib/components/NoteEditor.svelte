<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Eye, EyeOff, Save, Trash2, X, Plus } from 'lucide-svelte';
  import TagChip from './TagChip.svelte';
  import { aiSuggestions, fetchAISuggestions } from '$lib/stores/notes';
  import type { Note } from '$lib/api';

  export let note: Note | null = null;

  let title = note?.title ?? '';
  let content = note?.content ?? '';
  let tags: string[] = note?.tags ?? [];
  let tagInput = '';
  let saving = false;
  let saved = false;
  let previewMode = false;
  let aiTimeout: ReturnType<typeof setTimeout>;

  const dispatch = createEventDispatcher<{
    save: { title: string; content: string; tags: string[] };
    cancel: void;
    delete: void;
  }>();

  // Simple markdown → HTML renderer (no dependency needed)
  function renderMarkdown(md: string): string {
    return md
      // Code blocks
      .replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code class="lang-$1">$2</code></pre>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Headers
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Bold / italic
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      // Obsidian wiki-links → styled spans
      .replace(/\[\[([^\]]+)\]\]/g, '<span class="wikilink">$1</span>')
      // Checkboxes
      .replace(/^- \[x\] (.+)$/gm, '<div class="task done">✓ $1</div>')
      .replace(/^- \[ \] (.+)$/gm, '<div class="task">○ $1</div>')
      // Unordered list
      .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
      // Blockquote
      .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
      // Horizontal rule
      .replace(/^---$/gm, '<hr>')
      // Paragraphs (double newline)
      .replace(/\n\n+/g, '</p><p>')
      .replace(/^(?!<[a-z])/gm, '')
  }

  $: wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
  $: charCount = content.length;
  $: renderedHtml = renderMarkdown(content);

  function addTag(t: string) {
    const clean = t.trim().toLowerCase();
    if (clean && !tags.includes(clean)) tags = [...tags, clean];
    tagInput = '';
  }

  function removeTag(t: string) { tags = tags.filter(x => x !== t); }

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

  async function handleSave() {
    if (!title.trim()) return;
    saving = true;
    dispatch('save', { title: title.trim(), content, tags });
    saving = false;
    saved = true;
    setTimeout(() => (saved = false), 2000);
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
  }
</script>

<svelte:window on:keydown={onKeydown} />

<div class="editor-shell">
  <!-- Toolbar -->
  <div class="toolbar">
    <div class="toolbar-left">
      {#if note}
        <span class="note-source">{note.source === 'obsidian' ? '⬡ obsidian' : '◆ joidy'}</span>
      {:else}
        <span class="note-source">nueva nota</span>
      {/if}
    </div>

    <div class="toolbar-right">
      <span class="stat">{wordCount} palabras</span>
      <span class="stat">{charCount} chars</span>

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
        <span>{saved ? 'Guardado' : saving ? '...' : note ? 'Guardar' : 'Crear'}</span>
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
      <TagChip {tag} removable on:remove={(e) => removeTag(e.detail)} />
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
      <div class="preview" on:dblclick={() => previewMode = false}>
        {@html renderedHtml}
      </div>
    {:else}
      <textarea
        class="content-textarea"
        bind:value={content}
        on:input={onContentChange}
        placeholder="Escribe en markdown... (Ctrl+S para guardar, Ctrl+P para preview)"
        spellcheck="false"
      ></textarea>
    {/if}
  </div>
</div>

<style>
  .editor-shell {
    display: flex;
    flex-direction: column;
    height: 100%;
    width: 100%;
    overflow: hidden;
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
  }

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

  .danger-btn { color: var(--error); border-color: transparent; }
  .danger-btn:hover { border-color: var(--error); background: transparent; }

  /* ── Title ── */
  .title-row {
    padding: 20px 24px 12px;
    border-bottom: 1px solid var(--border-light, var(--border));
    flex-shrink: 0;
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

  .content-textarea {
    flex: 1;
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
    color: var(--text-primary);
    tab-size: 2;
  }
  .content-textarea::placeholder { color: var(--text-muted); }

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

  .preview :global(h1) { font-size: 20px; font-weight: 400; margin: 0 0 12px; color: var(--text-primary); }
  .preview :global(h2) { font-size: 16px; font-weight: 400; margin: 16px 0 8px; color: var(--text-primary); border-bottom: 1px solid var(--border); padding-bottom: 4px; }
  .preview :global(h3) { font-size: 14px; font-weight: 400; margin: 12px 0 6px; color: var(--text-secondary); }
  .preview :global(code) { font-family: var(--font-mono); font-size: 12px; background: var(--elevated); padding: 1px 5px; border-radius: 2px; color: var(--xp); }
  .preview :global(pre) { background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r); padding: 16px; overflow-x: auto; margin: 12px 0; }
  .preview :global(pre code) { background: none; padding: 0; color: var(--text-primary); }
  .preview :global(blockquote) { border-left: 2px solid var(--border); margin: 0; padding: 4px 12px; color: var(--text-secondary); font-style: italic; }
  .preview :global(li) { margin: 4px 0; padding-left: 12px; list-style: none; }
  .preview :global(li)::before { content: "—"; margin-right: 8px; color: var(--text-muted); }
  .preview :global(hr) { border: none; border-top: 1px solid var(--border); margin: 16px 0; }
  .preview :global(strong) { font-weight: 600; }
  .preview :global(p) { margin: 0 0 12px; }
  .preview :global(.wikilink) { color: var(--xp); border-bottom: 1px solid color-mix(in srgb, var(--xp) 40%, transparent); cursor: pointer; font-size: 13px; }
  .preview :global(.task) { font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); margin: 4px 0; }
  .preview :global(.task.done) { color: var(--success); }
</style>
