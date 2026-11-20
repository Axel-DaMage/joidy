<script lang="ts">
  // Raw markdown editing pane for the Goal Editor (#935). Owns the textarea,
  // line-number gutter and the rAF-based syntax highlight backdrop; content
  // itself lives in the shared `goalEditor` store.
  import { onDestroy } from 'svelte';
  import { t } from 'svelte-i18n';
  import { goalEditor } from '$lib/stores/goalEditor.svelte';

  interface Props {
    /** Called after each content edit so the container can trigger autosave. */
    oninput?: () => void;
  }

  let { oninput }: Props = $props();

  let lineCount = $derived(Math.max(1, goalEditor.content.split('\n').length));
  let lineNumbers = $derived(Array.from({ length: lineCount }, (_, i) => i + 1));

  let backdropEl = $state<HTMLElement | undefined>();
  let textareaEl = $state<HTMLTextAreaElement | undefined>();

  function syncScroll() {
    if (backdropEl && textareaEl) {
      backdropEl.scrollTop = textareaEl.scrollTop;
      backdropEl.scrollLeft = textareaEl.scrollLeft;
    }
  }

  function updateContent(e: Event) {
    goalEditor.content = (e.currentTarget as HTMLTextAreaElement).value;
    oninput?.();
  }

  function highlightMarkdown(text: string): string {
    if (!text) return '';
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    html = html.replace(/^(#{1,6})(\s+.+)$/gm, (match, hashes, rest) => {
      const level = hashes.length;
      return `<span style="color: var(--md-h${level}); font-weight: 500;">${hashes}${rest}</span>`;
    });

    html = html.replace(
      /^(\s*)([-*+]|\d+\.)(\s+)/gm,
      '$1<span style="color: var(--md-h1, var(--xp)); font-weight: bold;">$2</span>$3'
    );

    html = html.replace(
      /(\*\*|__)([^\s](?:.*?[^\s])?)\1/g,
      '<span style="font-weight: bold; color: var(--text-primary);">$1$2$1</span>'
    );
    html = html.replace(
      /(?<!\*)\*([^\s\*](?:.*?[^\s\*])?)\*(?!\*)/g,
      '<span style="font-style: italic; color: var(--text-secondary);">*$1*</span>'
    );
    html = html.replace(
      /(`)(.*?)\1/g,
      '<span style="background: var(--elevated); color: var(--md-h1, var(--xp)); border-radius: 3px; padding: 0 2px;">$1$2$1</span>'
    );
    html = html.replace(
      /(~~)([^\s](?:.*?[^\s])?)\1/g,
      '<span style="text-decoration: line-through; opacity: 0.6;">$1$2$1</span>'
    );

    if (html.endsWith('\n')) {
      html += '<br/>';
    }

    return html;
  }

  // Editor syntax highlight: update on the next animation frame instead of the
  // preview debounce. rAF coalesces multiple keystrokes into a single ~16ms
  // render, so typed characters are styled immediately without re-running the
  // regex highlighter more than once per frame (#703, #936).
  let editorHighlightedHtml = $state('');
  let highlightRaf: ReturnType<typeof requestAnimationFrame> | null = null;

  $effect(() => {
    const current = goalEditor.content;
    if (typeof requestAnimationFrame === 'function') {
      if (highlightRaf !== null) cancelAnimationFrame(highlightRaf);
      highlightRaf = requestAnimationFrame(() => {
        editorHighlightedHtml = highlightMarkdown(current);
        highlightRaf = null;
      });
    } else {
      editorHighlightedHtml = highlightMarkdown(current);
    }
  });

  onDestroy(() => {
    if (highlightRaf !== null) cancelAnimationFrame(highlightRaf);
  });
</script>

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
    value={goalEditor.content}
    oninput={updateContent}
    onscroll={syncScroll}
    placeholder={$t('goalEditor.contentPlaceholder')}
    aria-label={$t('goalEditor.contentPlaceholder')}
    spellcheck="false"></textarea>
</div>

<style>
  .editor-container {
    position: relative;
    flex: 1;
    width: 100%;
    height: 100%;
    min-height: 0;
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

  .content-textarea:focus-visible {
    outline: 2px solid var(--xp);
    outline-offset: -2px;
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
  .content-textarea::placeholder {
    color: var(--text-muted);
  }

  .content-textarea::selection {
    background: color-mix(in srgb, var(--xp) 30%, transparent);
    color: transparent;
  }
</style>
