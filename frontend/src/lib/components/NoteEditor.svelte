<script lang="ts">
  import { createEventDispatcher, onDestroy, onMount, tick, untrack } from 'svelte';
  import 'highlight.js/styles/github-dark.css';
  import NoteEditorToolbar from './NoteEditorToolbar.svelte';
  import NoteTagsBar from './NoteTagsBar.svelte';
  import NoteEditorContent from './NoteEditorContent.svelte';
  import NoteTitleRow from './NoteTitleRow.svelte';
  import NoteRecoveryBanner from './NoteRecoveryBanner.svelte';
  import { fetchAISuggestions } from '$lib/stores/notes';
  import { showFrontmatter, hideTagsLine } from '$lib/stores/settings';
  import { api, type Note } from '$lib/api';
  import { extractTagsFromContent } from '$lib/utils/noteContent';
  import { computeFormatEdit, applyWysiwygFormat, insertTextAt } from '$lib/utils/markdownFormat';
  import { UndoHistory } from '$lib/utils/undoHistory';
  import { loadDraft, persistDraft, clearDraft } from '$lib/utils/noteDrafts';
  import { handleEditorKeydown } from '$lib/utils/editorKeys';
  import type WysiwygEditor from './WysiwygEditor.svelte';

  const AUTOSAVE_DELAY = 2000;
  const DRAFT_PREFIX = 'joidy-draft-';

  interface NoteEditorProps {
    note?: Note | null;
    momentary?: boolean;
    hasPrev?: boolean;
    hasNext?: boolean;
    initialTitle?: string;
  }

  let {
    note = null,
    momentary = false,
    hasPrev = false,
    hasNext = false,
    initialTitle = '',
  }: NoteEditorProps = $props();

  let title = $state('');
  let content = $state('');
  let tags = $state<string[]>([]);
  let previousContentTags = $state<string[]>([]);

  // Sync editor state when the `note` prop changes. The body reads `content`
  // and `tags` (via extractTagsFromContent / tags.includes) after writing them,
  // which would create a self-dependency loop: tags = [...note.tags] makes a
  // new array reference every run, the read re-triggers the effect, and it
  // never converges. Wrap the writes in untrack() so only `note` is a
  // dependency — user edits to content/tags no longer reset the editor.
  $effect(() => {
    const n = note;
    if (!n) return;
    untrack(() => {
      title = n.title ?? initialTitle;
      content = n.content ?? '';
      tags = [...(n.tags || [])];
      previousContentTags = extractTagsFromContent(content);
      for (const t of previousContentTags) {
        if (!tags.includes(t)) tags.push(t);
      }
      history.reset(content || '');
    });
  });
  let saving = $state(false);
  let saved = $state(false);
  let previewMode = $state(false);
  let wysiwygMode = $state(false);
  let wysiwygRef = $state<WysiwygEditor | undefined>();
  let textareaEl = $state<HTMLTextAreaElement | undefined>();
  let aiTimeout: ReturnType<typeof setTimeout>;
  let autosaveTimer: ReturnType<typeof setTimeout> | undefined;
  let hasUnsavedChanges = $state(false);
  let showRecoveryPrompt = $state(false);
  let recoveredDraft = $state<{ title: string; content: string; tags: string[] } | null>(null);
  let savedTimer: ReturnType<typeof setTimeout> | undefined;

  let draftKey = $derived(note ? `${DRAFT_PREFIX}${note.id}` : null);

  const history = new UndoHistory();

  function scheduleSnapshot() {
    history.schedule(() => content);
  }

  function handleUndo() {
    const snapshot = history.undo();
    if (snapshot === undefined) return;
    content = snapshot;
    tags = extractTagsFromContent(content) || note?.tags?.slice() || [];
  }

  function handleRedo() {
    const snapshot = history.redo();
    if (snapshot === undefined) return;
    content = snapshot;
    tags = extractTagsFromContent(content) || note?.tags?.slice() || [];
  }

  let backlinks = $state<Note[]>([]);
  let similarNotes = $state<{ note: Note; score: number }[]>([]);

  // Fetch backlinks and semantically similar notes on mount or when note changes
  $effect(() => {
    if (note) {
      api.notes
        .backlinks(note.id)
        .then((res) => (backlinks = res))
        .catch(() => (backlinks = []));
      api.notes
        .similar(note.id, 5)
        .then((res) => (similarNotes = res))
        .catch(() => (similarNotes = []));
    } else {
      backlinks = [];
      similarNotes = [];
    }
  });

  const dispatch = createEventDispatcher<{
    save: { title: string; content: string; tags: string[] };
    cancel: void;
    delete: void;
    click: string;
    prev: void;
    next: void;
  }>();

  let rawFrontmatterMatch = $derived(content.match(/^---\r?\n[\s\S]*?\r?\n---/));
  let rawFrontmatter = $derived(rawFrontmatterMatch ? rawFrontmatterMatch[0] : '');

  let tagsLineMatch = $derived(content.match(/^#\s*Tags?:\s*.*$/im));
  let currentTagsLine = $derived(tagsLineMatch ? tagsLineMatch[0] : '');

  let visibleEditorContent = $derived(
    (() => {
      let val = content;
      if (!$showFrontmatter && rawFrontmatter) {
        val = val.replace(/^---\r?\n[\s\S]*?\r?\n---[\r\n]*/, '');
      }
      if ($hideTagsLine && tags.length > 0 && currentTagsLine) {
        val = val.replace(/^#\s*Tags?:\s*.*$/im, '').trim();
      }
      return val;
    })()
  );

  // Cheap computations stay on visibleEditorContent (instant feedback)
  let wordCount = $derived(
    visibleEditorContent.trim() ? visibleEditorContent.trim().split(/\s+/).length : 0
  );
  let charCount = $derived(visibleEditorContent.length);

  function onContentChange() {
    triggerAutosave();
    if (!note || content.length < 20) return;
    clearTimeout(aiTimeout);
    aiTimeout = setTimeout(() => {
      if (note) fetchAISuggestions(note.id, content, tags);
    }, 2000);
  }

  function saveDraft() {
    if (!draftKey || !title.trim()) return;
    persistDraft(draftKey, { title: title.trim(), content, tags });
  }

  function triggerAutosave() {
    hasUnsavedChanges = true;
    clearTimeout(autosaveTimer);
    autosaveTimer = setTimeout(() => {
      if (title.trim()) {
        saveDraft();
        handleSave();
      }
      hasUnsavedChanges = false;
    }, AUTOSAVE_DELAY);
  }

  onMount(() => {
    const draft = loadDraft(draftKey);
    if (draft && draft.content !== content) {
      recoveredDraft = draft;
      showRecoveryPrompt = true;
    }
  });

  function applyDraft() {
    if (recoveredDraft) {
      title = recoveredDraft.title;
      content = recoveredDraft.content;
      tags = recoveredDraft.tags;
      showRecoveryPrompt = false;
      recoveredDraft = null;
      triggerAutosave();
    }
  }

  function dismissDraft() {
    showRecoveryPrompt = false;
    recoveredDraft = null;
    if (draftKey) clearDraft(draftKey);
  }

  onDestroy(() => {
    clearTimeout(aiTimeout);
    clearTimeout(autosaveTimer);
    history.clear();
    clearTimeout(savedTimer);
    if (draftKey && title.trim()) {
      saveDraft();
    }
  });

  async function handleSave() {
    if (!title.trim()) return;
    saving = true;
    dispatch('save', { title: title.trim(), content, tags });
    saving = false;
    saved = true;
    clearDraft(draftKey);
    hasUnsavedChanges = false;
    clearTimeout(savedTimer);
    savedTimer = setTimeout(() => (saved = false), 2000);
  }

  function onKeydown(e: KeyboardEvent) {
    handleEditorKeydown(e, {
      save: handleSave,
      undo: handleUndo,
      redo: handleRedo,
      togglePreview: () => (previewMode = !previewMode),
      toggleWysiwyg: () => (wysiwygMode = !wysiwygMode),
      exitZen: () => (zenMode = false),
      zenMode,
      hasPrev,
      hasNext,
      prev: () => dispatch('prev'),
      next: () => dispatch('next'),
    });
  }

  let zenMode = $state(false);

  // Sync zen mode with a body class so the layout (nav, header, footer, sidebar)
  // can be hidden via CSS — not just covered by an overlay (#270).
  $effect(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.toggle('zen-mode-active', zenMode);
    }
  });

  onDestroy(() => {
    if (typeof document !== 'undefined') {
      document.body.classList.remove('zen-mode-active');
    }
  });

  function formatMarkdown(type: string) {
    if (wysiwygMode && wysiwygRef) {
      applyWysiwygFormat(wysiwygRef, type);
      return;
    }
    if (!textareaEl) return;
    const res = computeFormatEdit(
      content,
      textareaEl.selectionStart,
      textareaEl.selectionEnd,
      type
    );
    if (!res) return;
    content = res.content;

    tick().then(() => {
      textareaEl?.focus();
      textareaEl?.setSelectionRange(res.caret, res.caret);
    });
  }

  function insertAtCursor(text: string) {
    if (wysiwygMode && wysiwygRef) {
      wysiwygRef.insertContent(text);
      return;
    }
    if (!textareaEl) return;
    const res = insertTextAt(content, textareaEl.selectionStart, textareaEl.selectionEnd, text);
    content = res.content;
    tick().then(() => {
      textareaEl?.focus();
      textareaEl?.setSelectionRange(res.caret, res.caret);
    });
  }
</script>

<svelte:window onkeydown={onKeydown} />

<div class="editor-shell" class:zen-mode={zenMode}>
  <NoteRecoveryBanner
    bind:show={showRecoveryPrompt}
    onApply={applyDraft}
    onDismiss={dismissDraft}
  />

  <!-- Toolbar -->
  <NoteEditorToolbar
    {note}
    {momentary}
    {hasPrev}
    {hasNext}
    bind:zenMode
    bind:wysiwygMode
    bind:previewMode
    {wordCount}
    {charCount}
    {saving}
    {saved}
    {hasUnsavedChanges}
    {title}
    {formatMarkdown}
    {insertAtCursor}
    {handleSave}
    onPrev={() => dispatch('prev')}
    onNext={() => dispatch('next')}
    onDelete={() => dispatch('delete')}
    onCancel={() => dispatch('cancel')}
  />

  <!-- Title -->
  <NoteTitleRow {note} bind:title bind:content {triggerAutosave} {onContentChange} {handleSave} />

  <!-- Tags bar -->
  <NoteTagsBar bind:tags bind:content bind:previousContentTags />

  <!-- Content area -->
  <NoteEditorContent
    bind:content
    bind:tags
    bind:previousContentTags
    bind:previewMode
    bind:wysiwygMode
    bind:wysiwygRef
    bind:textareaEl
    {visibleEditorContent}
    {currentTagsLine}
    {rawFrontmatter}
    {backlinks}
    {similarNotes}
    {scheduleSnapshot}
    {onContentChange}
    {handleSave}
  />
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
    z-index: var(--z-tooltip);
    background: var(--bg);
    padding-top: 40px;
  }
</style>
