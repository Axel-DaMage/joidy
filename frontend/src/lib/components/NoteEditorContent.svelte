<script lang="ts">
  import { onDestroy } from 'svelte';
  import WysiwygEditor from './WysiwygEditor.svelte';
  import NoteEditorPreview from './NoteEditorPreview.svelte';
  import { showFrontmatter, hideTagsLine } from '$lib/stores/settings';
  import { extractTagsFromContent } from '$lib/utils/noteContent';
  import { highlightMarkdown } from '$lib/utils/markdownHighlight';
  import type { Note } from '$lib/api';

  interface Props {
    content: string;
    tags: string[];
    previousContentTags: string[];
    previewMode: boolean;
    wysiwygMode: boolean;
    wysiwygRef: WysiwygEditor | undefined;
    textareaEl: HTMLTextAreaElement | undefined;
    visibleEditorContent: string;
    currentTagsLine: string;
    rawFrontmatter: string;
    backlinks: Note[];
    similarNotes: { note: Note; score: number }[];
    scheduleSnapshot: () => void;
    onContentChange: () => void;
    handleSave: () => void;
  }

  let {
    content = $bindable(),
    tags = $bindable(),
    previousContentTags = $bindable(),
    previewMode = $bindable(),
    wysiwygMode = $bindable(),
    wysiwygRef = $bindable(),
    textareaEl = $bindable(),
    visibleEditorContent,
    currentTagsLine,
    rawFrontmatter,
    backlinks,
    similarNotes,
    scheduleSnapshot,
    onContentChange,
    handleSave,
  }: Props = $props();

  let backdropEl = $state<HTMLElement | undefined>();
  let lineGutterEl = $state<HTMLElement | undefined>();

  function syncScroll() {
    if (backdropEl && textareaEl) {
      backdropEl.scrollTop = textareaEl.scrollTop;
      backdropEl.scrollLeft = textareaEl.scrollLeft;
    }
    if (lineGutterEl && textareaEl) {
      lineGutterEl.scrollTop = textareaEl.scrollTop;
    }
  }

  // Cheap computations stay on visibleEditorContent (instant feedback)
  let lineCount = $derived(Math.max(1, visibleEditorContent.split('\n').length));
  let lineNumbers = $derived(Array.from({ length: lineCount }, (_, i) => i + 1));

  function updateVisibleContent(e: Event) {
    const val = (e.currentTarget as HTMLTextAreaElement).value;
    scheduleSnapshot();
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
    const added = currentContentTags.filter((t) => !previousContentTags.includes(t));
    const removed = previousContentTags.filter((t) => !currentContentTags.includes(t));

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
        newTags = newTags.filter((x) => x !== r);
        tagsChanged = true;
      }
    }

    if (tagsChanged) tags = newTags;
    previousContentTags = currentContentTags;

    onContentChange();
  }

  function handleWysiwygChange(e: CustomEvent<string>) {
    const md = e.detail;
    scheduleSnapshot();
    let nextContent = md;

    if ($hideTagsLine && tags.length > 0 && currentTagsLine) {
      if (!nextContent.includes(currentTagsLine)) {
        nextContent = nextContent.trim() + '\n\n' + currentTagsLine;
      }
    }

    if (!$showFrontmatter && rawFrontmatter) {
      nextContent = rawFrontmatter + '\n\n' + nextContent.trim();
    }

    content = nextContent;
    onContentChange();
  }

  // Editor syntax highlight: update on the next animation frame instead of the
  // 300ms debounce. rAF coalesces multiple keystrokes into a single ~16ms
  // render, so typed characters are styled immediately without re-running the
  // regex highlighter more than once per frame (#703).
  let editorHighlightedHtml = $state('');
  let highlightRaf: ReturnType<typeof requestAnimationFrame> | null = null;

  $effect(() => {
    const current = visibleEditorContent;
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

<!-- Content area -->
<div class="content-area">
  {#if previewMode}
    <NoteEditorPreview {visibleEditorContent} {tags} {backlinks} {similarNotes} bind:previewMode />
  {:else if wysiwygMode}
    <WysiwygEditor
      bind:this={wysiwygRef}
      content={visibleEditorContent}
      placeholder="Escribe algo... (Ctrl+S para guardar)"
      oncontentchange={handleWysiwygChange}
      onsave={handleSave}
    />
  {:else}
    <div class="editor-container">
      <div class="line-gutter" bind:this={lineGutterEl} aria-hidden="true">
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
        value={visibleEditorContent}
        oninput={updateVisibleContent}
        onscroll={syncScroll}
        placeholder="Escribe en markdown... (Ctrl+S para guardar, Ctrl+P para preview)"
        spellcheck="false"></textarea>
    </div>
  {/if}
</div>

<style>
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
  .content-textarea::placeholder {
    color: var(--text-muted);
  }

  /* Style selection to be visible over transparent text */
  .content-textarea::selection {
    background: color-mix(in srgb, var(--xp) 30%, transparent);
    color: transparent;
  }
</style>
