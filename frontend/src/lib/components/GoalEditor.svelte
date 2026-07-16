<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { Eye, EyeOff, Save, Trash2, X, Maximize, ChevronLeft, ChevronRight, Settings } from 'lucide-svelte';
  import { marked } from 'marked';
  import DOMPurify from 'dompurify';
  import { api, type Goal } from '$lib/api';

  marked.use({ gfm: true, breaks: true });

  DOMPurify.setConfig({
    ALLOWED_TAGS: [
      'p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li',
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
      'pre', 'code', 'blockquote',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'span', 'div', 'hr', 'img', 'del', 'ins', 'sup', 'sub',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt', 'class', 'data-title'],
  });

  export let goal: Goal | null = null;
  export let content: string = '';

  const dispatch = createEventDispatcher<{
    save: { title: string; content: string };
    cancel: void;
    delete: void;
    edit: void;
  }>();

  let title = goal?.title ?? '';
  let saving = false;
  let saved = false;
  let previewMode = false;
  let zenMode = false;

  $: if (goal) {
    title = goal.title;
  }

  $: visibleContent = content;
  $: wordCount = visibleContent.trim() ? visibleContent.trim().split(/\s+/).length : 0;
  $: charCount = visibleContent.length;
  $: renderedHtml = renderMarkdown(visibleContent);
  $: lineCount = Math.max(1, visibleContent.split('\n').length);
  $: lineNumbers = Array.from({ length: lineCount }, (_, i) => i + 1);

  function renderMarkdown(md: string): string {
    if (!md.trim()) return '<p style="color:var(--text-muted);font-style:italic;">Escribe algo para ver el preview...</p>';
    return DOMPurify.sanitize(String(marked.parse(md)));
  }

  function updateContent(e: Event) {
    content = (e.currentTarget as HTMLTextAreaElement).value;
    wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;
    charCount = content.length;
    renderedHtml = renderMarkdown(content);
  }

  async function handleSave() {
    if (!title.trim()) return;
    saving = true;
    dispatch('save', { title: title.trim(), content });
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
    if (e.key === 'Escape' && zenMode) {
      e.preventDefault();
      e.stopPropagation();
      zenMode = false;
    }
  }

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

    html = html.replace(/^(#{1,6})(\s+.+)$/gm, (match, hashes, rest) => {
      const level = hashes.length;
      return `<span style="color: var(--md-h${level}); font-weight: 500;">${hashes}${rest}</span>`;
    });

    html = html.replace(/^(\s*)([-*+]|\d+\.)(\s+)/gm, '$1<span style="color: var(--md-h1, var(--xp)); font-weight: bold;">$2</span>$3');

    html = html.replace(/(\*\*|__)([^\s](?:.*?[^\s])?)\1/g, '<span style="font-weight: bold; color: var(--text-primary);">$1$2$1</span>');
    html = html.replace(/(?<!\*)\*([^\s\*](?:.*?[^\s\*])?)\*(?!\*)/g, '<span style="font-style: italic; color: var(--text-secondary);">*$1*</span>');
    html = html.replace(/(`)(.*?)\1/g, '<span style="background: var(--elevated); color: var(--md-h1, var(--xp)); border-radius: 3px; padding: 0 2px;">$1$2$1</span>');
    html = html.replace(/(~~)([^\s](?:.*?[^\s])?)\1/g, '<span style="text-decoration: line-through; opacity: 0.6;">$1$2$1</span>');

    if (html.endsWith('\n')) {
      html += '<br/>';
    }

    return html;
  }

  $: editorHighlightedHtml = highlightMarkdown(visibleContent);
</script>

<svelte:window on:keydown={onKeydown} />

<div class="editor-shell" class:zen-mode={zenMode}>
  {#if !zenMode}
  <div class="toolbar">
    <div class="toolbar-left">
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

      <button
        class="toolbar-btn"
        class:active={previewMode}
        on:click={() => previewMode = !previewMode}
        title="Alternar preview (Ctrl+P)"
      >
        {#if previewMode}<EyeOff size={14} />{:else}<Eye size={14} />{/if}
        <span>{previewMode ? 'Editor' : 'Vista previa'}</span>
      </button>

      <button
        class="toolbar-btn save-btn"
        class:saved
        on:click={handleSave}
        disabled={saving || !title.trim()}
        title="Guardar (Ctrl+S)"
      >
        <Save size={14} />
        <span class="save-status">{saved ? 'Guardado' : saving ? '...' : 'Guardar'}</span>
      </button>

      <button class="toolbar-btn" on:click={() => dispatch('edit')} title="Editar ajustes del objetivo">
        <Settings size={14} />
        <span>Ajustes</span>
      </button>

      <button class="toolbar-btn" on:click={() => dispatch('cancel')} title="Cerrar">
        <X size={14} />
      </button>
    </div>
  </div>
  {/if}

  <div class="title-row">
    <input
      class="title-input"
      bind:value={title}
      placeholder="Título del objetivo..."
      on:keydown={(e) => e.key === 'Enter' && handleSave()}
    />
  </div>

  <div class="content-area">
    {#if previewMode}
      <div class="preview" on:dblclick={() => previewMode = false}>
        {@html renderedHtml}
      </div>
    {:else}
      <div class="editor-container">
        <div class="line-gutter" aria-hidden="true">
          {#each lineNumbers as line}
            <div class="line-number">{line}</div>
          {/each}
        </div>
        <div class="backdrop" bind:this={backdropEl} aria-hidden="true">
          <div class="highlights">{@html editorHighlightedHtml}</div>
        </div>
        <textarea
          class="content-textarea"
          bind:this={textareaEl}
          value={content}
          on:input={updateContent}
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
    border: 1px solid var(--border);
    border-radius: var(--r);
    overflow: hidden;
  }

  .editor-shell.zen-mode {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    z-index: 9999;
    border: none;
    border-radius: 0;
    background: var(--bg);
    padding-top: 40px;
  }

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

  .toolbar-left, .toolbar-right {
    display: flex;
    align-items: center;
    gap: var(--s2);
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
  .save-btn:hover { background: var(--accent); color: var(--accent-contrast-text, var(--bg)); }
  .save-btn.saved { background: var(--success); border-color: var(--success); color: var(--text-primary); }

  .save-status {
    display: inline-block;
    min-width: 58px;
    text-align: center;
  }

  .title-input {
    flex: 1;
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

  .title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 20px 24px 12px;
    border-bottom: 1px solid var(--border-light, var(--border));
    flex-shrink: 0;
  }

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

  .line-gutter {
    position: absolute;
    top: 0;
    left: 0;
    width: 44px;
    height: 100%;
    padding: 24px 0;
    background: var(--surface);
    border-right: 1px solid var(--border-light, var(--border));
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-muted);
    text-align: right;
    overflow: hidden;
    pointer-events: none;
  }

  .line-number {
    height: 1.7em;
    line-height: 1.7;
    padding-right: 10px;
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
    padding: 24px 24px 24px 60px;
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
    padding: 24px 24px 24px 60px;
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

  .content-textarea::selection {
    background: color-mix(in srgb, var(--xp) 30%, transparent);
    color: transparent;
  }

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
  .preview :global(p) { margin: 0 0 12px; }
  .preview :global(ul) { margin: 0 0 12px; padding-left: 20px; }
  .preview :global(li) { margin: 4px 0; }
  .preview :global(code) { font-family: var(--font-mono); font-size: 12px; background: var(--elevated); padding: 1px 5px; border-radius: 2px; color: var(--md-h1, var(--xp)); }
  .preview :global(pre) { background: var(--elevated); border: 1px solid var(--border); border-radius: var(--r); padding: 16px; overflow-x: auto; margin: 12px 0; }
  .preview :global(blockquote) { border-left: 2px solid var(--border); margin: 0; padding: 4px 12px; color: var(--text-secondary); font-style: italic; }
  .preview :global(strong) { font-weight: 600; }
  .preview :global(em) { font-style: italic; }
  .preview :global(del) { text-decoration: line-through; color: var(--text-muted); }
</style>