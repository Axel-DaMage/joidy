<script lang="ts">
  import { untrack } from 'svelte';
  import { renderMarkdown as renderMarkdownUtil } from '$lib/utils/markdown';
  import { hideTagsLine } from '$lib/stores/settings';
  import { findNoteByTitle } from '$lib/stores/notes';
  import { goto } from '$app/navigation';
  import { logger } from '$lib/utils/logger';
  import type { Note } from '$lib/api';

  interface Props {
    visibleEditorContent: string;
    tags: string[];
    backlinks: Note[];
    similarNotes: { note: Note; score: number }[];
    previewMode: boolean;
  }

  let {
    visibleEditorContent,
    tags,
    backlinks,
    similarNotes,
    previewMode = $bindable(),
  }: Props = $props();

  // Debounced content for the expensive full markdown render (preview mode:
  // marked + DOMPurify + highlight.js). The editor syntax highlight uses a
  // faster rAF-based update (see editorHighlightedHtml) so typed text is styled
  // immediately instead of lagging 300ms (#703).
  // Seed with the current value so the first preview render is instant (the
  // continuous debounce effect below keeps it updated afterwards).
  let debouncedContent = $state(untrack(() => visibleEditorContent));
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    const current = visibleEditorContent;
    // Clear the pending debounce on every re-run AND on component teardown (#1003).
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      debouncedContent = current;
    }, 300);
    return () => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = null;
    };
  });

  // Markdown → HTML via the shared utility (handles tables, blockquotes, lists,
  // wikilinks, syntax highlighting, and DOMPurify sanitization).
  function renderMarkdown(md: string): string {
    return renderMarkdownUtil(md, {
      hideTagsLine: $hideTagsLine,
      hasTags: tags.length > 0,
    });
  }

  // Expensive computations use debouncedContent (300ms after last keystroke)
  let renderedHtml = $derived(renderMarkdown(debouncedContent));

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
          logger.log('Note not found:', title);
        }
      }
    }
  }
</script>

<div
  class="preview"
  ondblclick={() => (previewMode = false)}
  onclick={handlePreviewClick}
  onkeydown={(e) =>
    (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), (previewMode = false))}
  role="button"
  tabindex="0"
>
  {@html renderedHtml}

  {#if backlinks.length > 0}
    <div class="backlinks-section">
      <h5 class="mono">ENLACES ENTRANTES</h5>
      <div class="backlinks-grid">
        {#each backlinks as bl}
          <button class="backlink-card" onclick={() => goto(`/notes?id=${bl.id}`)}>
            <span class="bl-title">{bl.title}</span>
            <span class="bl-meta mono">{bl.source === 'obsidian' ? '⬡' : '◆'}</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if similarNotes.length > 0}
    <div class="backlinks-section">
      <h5 class="mono">NOTAS RELACIONADAS (SEMÁNTICO)</h5>
      <div class="backlinks-grid">
        {#each similarNotes as result}
          <button class="backlink-card" onclick={() => goto(`/notes?id=${result.note.id}`)}>
            <span class="bl-title">{result.note.title}</span>
            <span class="bl-meta mono">{(result.score * 100).toFixed(0)}%</span>
          </button>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
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

  .preview :global(h1) {
    font-size: 20px;
    font-weight: 500;
    margin: 0 0 12px;
    color: var(--md-h1, var(--text-primary));
  }
  .preview :global(h2) {
    font-size: 16px;
    font-weight: 500;
    margin: 16px 0 8px;
    color: var(--md-h2, var(--text-primary));
    border-bottom: 1px solid var(--border);
    padding-bottom: 4px;
  }
  .preview :global(h3) {
    font-size: 14px;
    font-weight: 500;
    margin: 12px 0 6px;
    color: var(--md-h3, var(--text-secondary));
  }
  .preview :global(h4) {
    font-size: 13px;
    font-weight: 500;
    margin: 10px 0 4px;
    color: var(--md-h4, var(--text-secondary));
  }
  .preview :global(h5) {
    font-size: 12px;
    font-weight: 600;
    margin: 8px 0 2px;
    color: var(--md-h5, var(--text-muted));
  }
  .preview :global(h6) {
    font-size: 11px;
    font-weight: 700;
    margin: 8px 0 2px;
    color: var(--md-h6, var(--text-muted));
    text-transform: uppercase;
  }
  .preview :global(code) {
    font-family: var(--font-mono);
    font-size: 12px;
    background: var(--elevated);
    padding: 1px 5px;
    border-radius: 2px;
    color: var(--md-h1, var(--xp));
  }
  .preview :global(pre) {
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    padding: 16px;
    overflow-x: auto;
    margin: 12px 0;
    white-space: pre;
  }
  .preview :global(pre code) {
    background: none;
    padding: 0;
    color: var(--text-primary);
    white-space: pre;
  }
  .preview :global(blockquote) {
    border-left: 2px solid var(--border);
    margin: 0;
    padding: 4px 12px;
    color: var(--text-secondary);
    font-style: italic;
  }
  .preview :global(li) {
    margin: 4px 0;
    padding-left: 4px;
    list-style: disc;
  }
  .preview :global(ul) {
    padding-left: 20px;
    margin: 0 0 12px;
  }
  .preview :global(ol) {
    padding-left: 20px;
    margin: 0 0 12px;
  }
  .preview :global(hr) {
    border: none;
    border-top: 1px solid var(--border);
    margin: 16px 0;
  }
  .preview :global(strong) {
    font-weight: 600;
  }
  .preview :global(p) {
    margin: 0 0 12px;
  }
  .preview :global(.wikilink) {
    color: var(--xp);
    border-bottom: 1px solid color-mix(in srgb, var(--xp) 40%, transparent);
    cursor: pointer;
    transition: border-bottom-color var(--t-fast);
  }
  .preview :global(.wikilink:hover) {
    border-bottom-color: var(--xp);
  }

  .backlinks-section {
    margin-top: 40px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
  }
  .backlinks-section h5 {
    font-size: 10px;
    color: var(--text-muted);
    margin-bottom: 12px;
    letter-spacing: 0.1em;
  }
  .backlinks-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .backlink-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    background: var(--elevated);
    border: 1px solid var(--border);
    border-radius: var(--r);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  .backlink-card:hover {
    border-color: var(--text-secondary);
    background: var(--hover);
  }
  .bl-title {
    font-size: 12px;
    color: var(--text-primary);
  }
  .bl-meta {
    font-size: 10px;
    color: var(--text-muted);
  }
  .preview :global(.task) {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    margin: 4px 0;
  }
  .preview :global(.task.done) {
    color: var(--success);
  }

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
  .preview :global(tr:last-child td) {
    border-bottom: none;
  }
  .preview :global(tr:hover td) {
    background: var(--elevated);
  }

  /* ── Task lists (marked renders - [x] as <input type="checkbox">) ── */
  .preview :global(input[type='checkbox']) {
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
  .preview :global(input[type='checkbox']:checked) {
    background: var(--success);
    border-color: var(--success);
  }
  .preview :global(input[type='checkbox']:checked::after) {
    content: '✓';
    position: absolute;
    top: -2px;
    left: 1px;
    font-size: 9px;
    color: var(--bg);
  }
  .preview :global(.task-list-item) {
    list-style: none;
    padding-left: 0;
  }
  .preview :global(.task-list-item)::before {
    content: none;
  }

  /* ── Strikethrough (GFM) ── */
  .preview :global(del) {
    text-decoration: line-through;
    color: var(--text-muted);
  }

  /* ── Links ── */
  .preview :global(a) {
    color: var(--xp);
    text-decoration: none;
    border-bottom: 1px solid color-mix(in srgb, var(--xp) 35%, transparent);
  }
  .preview :global(a:hover) {
    border-bottom-color: var(--xp);
  }
</style>
