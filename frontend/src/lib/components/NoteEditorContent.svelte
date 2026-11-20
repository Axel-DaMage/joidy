<script lang="ts">
  import { onDestroy } from 'svelte';
  import WysiwygEditor from './WysiwygEditor.svelte';
  import NoteEditorPreview from './NoteEditorPreview.svelte';
  import { showFrontmatter, hideTagsLine } from '$lib/stores/settings';
  import { extractTagsFromContent, recomposeHiddenSlices } from '$lib/utils/noteContent';
  import { highlightMarkdown } from '$lib/utils/markdownHighlight';
  import { t } from 'svelte-i18n';
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

  // Cheap computations stay on visibleEditorContent (instant feedback).
  // countLines avoids the full split() array allocation on every keystroke —
  // on a 2,000-line note that is a 2,000-element array per character (#1311).
  function countLines(s: string): number {
    let n = 1;
    for (let i = 0; i < s.length; i++) if (s.charCodeAt(i) === 10) n++;
    return n;
  }
  let lineCount = $derived(countLines(visibleEditorContent));
  // One pre-formatted text node replaces the old {#each} of one div per line
  // (2,000+ DOM nodes recreated on every newline on large notes, #1311).
  let lineNumbersText = $derived(
    Array.from({ length: lineCount }, (_, i) => i + 1).join('\n')
  );

  // Tag extraction runs two regex sweeps over the entire document — debounce
  // it instead of scanning 100KB+ per keystroke (#1311). A trailing call
  // keeps tags in sync; flushTagSync() forces it before save/destroy.
  let tagSyncTimer: ReturnType<typeof setTimeout> | null = null;

  function syncTagsFromContent() {
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
  }

  function scheduleTagSync() {
    if (tagSyncTimer) clearTimeout(tagSyncTimer);
    tagSyncTimer = setTimeout(() => {
      tagSyncTimer = null;
      syncTagsFromContent();
    }, 300);
  }

  // Flushes any pending tag sync — called by NoteEditor before saving so a
  // `# Tags:` line typed <300ms before Ctrl+S is not lost (#1311).
  export function flushTagSync() {
    if (tagSyncTimer) {
      clearTimeout(tagSyncTimer);
      tagSyncTimer = null;
      syncTagsFromContent();
    }
  }

  function updateVisibleContent(e: Event) {
    const val = (e.currentTarget as HTMLTextAreaElement).value;
    scheduleSnapshot();
    content = recomposeHiddenSlices(val, {
      tagsLine: $hideTagsLine && tags.length > 0 ? currentTagsLine : '',
      frontmatter: !$showFrontmatter ? rawFrontmatter : '',
    });

    scheduleTagSync();
    onContentChange();
  }

  // The WYSIWYG editor never receives the frontmatter block: marked parses
  // `---` as setext/`<hr>` and turndown can't emit YAML back, so a round-trip
  // would corrupt it. It's re-attached on every change instead — regardless
  // of the showFrontmatter preference (#1304).
  let wysiwygContent = $derived(
    visibleEditorContent.replace(/^---\r?\n[\s\S]*?\r?\n---[\r\n]*/, '')
  );

  function handleWysiwygChange(e: CustomEvent<string>) {
    const md = e.detail;
    scheduleSnapshot();
    content = recomposeHiddenSlices(md, {
      tagsLine: $hideTagsLine && tags.length > 0 ? currentTagsLine : '',
      frontmatter: rawFrontmatter,
    });
    onContentChange();
  }

  // Editor syntax highlight: update on the next animation frame instead of the
  // 300ms debounce. rAF coalesces multiple keystrokes into a single ~16ms
  // render, so typed characters are styled immediately without re-running the
  // regex highlighter more than once per frame (#703). On very large notes the
  // regex pass is too heavy for a per-frame budget, so it trails at 250ms
  // instead — typing stays responsive and highlighting catches up on a pause
  // (#1311).
  const HIGHLIGHT_DEBOUNCE_THRESHOLD = 50_000; // chars
  let editorHighlightedHtml = $state('');
  let highlightRaf: ReturnType<typeof requestAnimationFrame> | null = null;
  let highlightTimer: ReturnType<typeof setTimeout> | null = null;

  $effect(() => {
    const current = visibleEditorContent;
    if (highlightTimer !== null) {
      clearTimeout(highlightTimer);
      highlightTimer = null;
    }
    if (current.length > HIGHLIGHT_DEBOUNCE_THRESHOLD) {
      highlightTimer = setTimeout(() => {
        editorHighlightedHtml = highlightMarkdown(current);
        highlightTimer = null;
      }, 250);
    } else if (typeof requestAnimationFrame === 'function') {
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
    if (highlightTimer !== null) clearTimeout(highlightTimer);
    if (tagSyncTimer) clearTimeout(tagSyncTimer);
    syncTagsFromContent();
  });
</script>

<!-- Content area -->
<div class="content-area">
  {#if previewMode}
    <NoteEditorPreview {visibleEditorContent} {tags} {backlinks} {similarNotes} bind:previewMode />
  {:else if wysiwygMode}
    <WysiwygEditor
      bind:this={wysiwygRef}
      content={wysiwygContent}
      placeholder="Escribe algo... (Ctrl+S para guardar)"
      oncontentchange={handleWysiwygChange}
      onsave={handleSave}
    />
  {:else}
    <div class="editor-container">
      <div class="line-gutter" bind:this={lineGutterEl} aria-hidden="true">
        <pre class="line-numbers">{lineNumbersText}</pre>
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
        aria-label={$t('noteEditor.contentLabel')}
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

  .line-numbers {
    margin: 0;
    font: inherit;
    line-height: 1.7;
    padding-right: 10px;
    text-align: right;
    user-select: none;
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

  /* The editor is borderless by design — keep a subtle keyboard-focus cue. */
  .content-textarea:focus-visible {
    outline: 2px solid color-mix(in srgb, var(--xp) 60%, transparent);
    outline-offset: -2px;
  }
</style>
