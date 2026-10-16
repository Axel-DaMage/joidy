<script lang="ts">
  import {
    Eye,
    EyeOff,
    Save,
    Trash2,
    X,
    ChevronLeft,
    ChevronRight,
    Bold,
    Italic,
    Strikethrough,
    Heading1,
    Heading2,
    Heading3,
    List,
    ListOrdered,
    Link,
    Quote,
    Code,
    Image,
    Paperclip,
    Type,
    Maximize,
  } from 'lucide-svelte';
  import { api, type Note } from '$lib/api';
  import { showNotification } from '$lib/stores/gamification';
  import NoteExportMenu from './NoteExportMenu.svelte';
  import { t } from 'svelte-i18n';

  interface Props {
    note: Note | null;
    momentary: boolean;
    hasPrev: boolean;
    hasNext: boolean;
    zenMode: boolean;
    wysiwygMode: boolean;
    previewMode: boolean;
    wordCount: number;
    charCount: number;
    saving: boolean;
    saved: boolean;
    hasUnsavedChanges: boolean;
    title: string;
    formatMarkdown: (type: string) => void;
    insertAtCursor: (text: string) => void;
    handleSave: () => void;
    onPrev: () => void;
    onNext: () => void;
    onDelete: () => void;
    onCancel: () => void;
  }

  let {
    note,
    momentary,
    hasPrev,
    hasNext,
    zenMode = $bindable(),
    wysiwygMode = $bindable(),
    previewMode = $bindable(),
    wordCount,
    charCount,
    saving,
    saved,
    hasUnsavedChanges,
    title,
    formatMarkdown,
    insertAtCursor,
    handleSave,
    onPrev,
    onNext,
    onDelete,
    onCancel,
  }: Props = $props();

  let imageInputEl = $state<HTMLInputElement | undefined>();
  let fileInputEl = $state<HTMLInputElement | undefined>();
  let uploading = $state(false);

  async function uploadAttachment(file: File, type: 'image' | 'file') {
    if (!file) return;
    uploading = true;
    try {
      const result = type === 'image' ? await api.upload.image(file) : await api.upload.file(file);
      const insertion =
        type === 'image'
          ? `![${result.filename}](${result.url})`
          : `[${result.filename}](${result.url})`;
      insertAtCursor(insertion);
      showNotification(`${type === 'image' ? 'Imagen' : 'Archivo'} subido`, 'success');
    } catch (e: any) {
      showNotification(e.message || 'Error subiendo archivo', 'error');
    } finally {
      uploading = false;
      if (imageInputEl) imageInputEl.value = '';
      if (fileInputEl) fileInputEl.value = '';
    }
  }

  async function handleImageUpload(e: Event) {
    const target = e.target as HTMLInputElement;
    const file = target.files?.[0];
    if (file) await uploadAttachment(file, 'image');
  }

  async function handleFileUpload(e: Event) {
    const target = e.target as HTMLInputElement;
    const file = target.files?.[0];
    if (file) await uploadAttachment(file, 'file');
  }

  function openImageUpload() {
    imageInputEl?.click();
  }

  function openFileUpload() {
    fileInputEl?.click();
  }
</script>

<!-- Toolbar -->
{#if !zenMode}
  <div class="toolbar">
    <div class="toolbar-left">
      {#if !momentary && note}
        <div class="nav-controls toolbar-nav">
          <button
            class="toolbar-btn icon-only"
            disabled={!hasPrev}
            onclick={onPrev}
            title={$t('noteEditor.prevNote')}
            aria-label={$t('noteEditor.prevNoteShort')}
          >
            <ChevronLeft size={14} />
          </button>
          <button
            class="toolbar-btn icon-only"
            disabled={!hasNext}
            onclick={onNext}
            title={$t('noteEditor.nextNote')}
            aria-label={$t('noteEditor.nextNoteShort')}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      {/if}

      <div class="format-divider"></div>

      <div class="format-toolbar">
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('bold')}
          title={$t('noteEditor.bold')}
          aria-label={$t('noteEditor.boldShort')}
        >
          <Bold size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('italic')}
          title={$t('noteEditor.italic')}
          aria-label={$t('noteEditor.italicShort')}
        >
          <Italic size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('strikethrough')}
          title={$t('noteEditor.strikethrough')}
          aria-label={$t('noteEditor.strikethrough')}
        >
          <Strikethrough size={13} />
        </button>

        <div class="format-divider"></div>

        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('h1')}
          title={$t('noteEditor.h1')}
          aria-label={$t('noteEditor.h1')}
        >
          <Heading1 size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('h2')}
          title={$t('noteEditor.h2')}
          aria-label={$t('noteEditor.h2')}
        >
          <Heading2 size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('h3')}
          title={$t('noteEditor.h3')}
          aria-label={$t('noteEditor.h3')}
        >
          <Heading3 size={13} />
        </button>

        <div class="format-divider"></div>

        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('ul')}
          title={$t('noteEditor.ul')}
          aria-label={$t('noteEditor.ul')}
        >
          <List size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('ol')}
          title={$t('noteEditor.ol')}
          aria-label={$t('noteEditor.ol')}
        >
          <ListOrdered size={13} />
        </button>

        <div class="format-divider"></div>

        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('link')}
          title={$t('noteEditor.link')}
          aria-label={$t('noteEditor.link')}
        >
          <Link size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('quote')}
          title={$t('noteEditor.quote')}
          aria-label={$t('noteEditor.quote')}
        >
          <Quote size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={() => formatMarkdown('code')}
          title={$t('noteEditor.code')}
          aria-label={$t('noteEditor.code')}
        >
          <Code size={13} />
        </button>

        <div class="format-divider"></div>

        <button
          class="toolbar-btn icon-only"
          onclick={openImageUpload}
          disabled={uploading}
          title={$t('noteEditor.image')}
          aria-label={$t('noteEditor.image')}
        >
          <Image size={13} />
        </button>
        <button
          class="toolbar-btn icon-only"
          onclick={openFileUpload}
          disabled={uploading}
          title={$t('noteEditor.file')}
          aria-label={$t('noteEditor.file')}
        >
          <Paperclip size={13} />
        </button>
      </div>
    </div>
    <input
      bind:this={imageInputEl}
      type="file"
      accept="image/*"
      style="display:none"
      onchange={handleImageUpload}
    />
    <input bind:this={fileInputEl} type="file" style="display:none" onchange={handleFileUpload} />

    <div class="toolbar-right">
      <span class="stat">{wordCount} palabras</span>
      <span class="stat">{charCount} caracteres</span>

      <button
        class="toolbar-btn icon-only"
        class:active={zenMode}
        onclick={() => (zenMode = !zenMode)}
        title={$t('noteEditor.zenMode')}
        aria-label={$t('noteEditor.zenModeShort')}
      >
        <Maximize size={14} />
      </button>

      <button
        class="toolbar-btn"
        class:active={wysiwygMode}
        onclick={() => (wysiwygMode = !wysiwygMode)}
        title={$t('noteEditor.wysiwyg')}
        aria-label={$t('noteEditor.wysiwygShort')}
      >
        <Type size={14} />
        <span>{wysiwygMode ? 'Raw' : 'Visual'}</span>
      </button>

      <button
        class="toolbar-btn"
        class:active={previewMode}
        onclick={() => (previewMode = !previewMode)}
        title={$t('noteEditor.preview')}
        aria-label={$t('noteEditor.previewShort')}
      >
        {#if previewMode}<EyeOff size={14} />{:else}<Eye size={14} />{/if}
        <span>{previewMode ? 'Editor' : 'Vista previa'}</span>
      </button>

      <button
        class="toolbar-btn save-btn"
        class:saved
        onclick={handleSave}
        disabled={saving || !title.trim()}
        title="Guardar (Ctrl+S)"
      >
        <Save size={14} />
        <span class="save-status"
          >{saved ? 'Guardado' : saving ? '...' : note ? 'Guardar' : 'Crear'}</span
        >
      </button>

      {#if hasUnsavedChanges && !saved}
        <span class="unsaved-indicator" title="Cambios sin guardar">·</span>
      {/if}

      {#if note}
        <NoteExportMenu {note} />

        <button
          class="toolbar-btn danger-btn"
          onclick={onDelete}
          title="Eliminar nota"
          aria-label="Eliminar nota"
        >
          <Trash2 size={14} />
        </button>
      {/if}

      <button class="toolbar-btn" onclick={onCancel} title="Cerrar" aria-label="Cerrar">
        <X size={14} />
      </button>
    </div>
  </div>
{/if}

<style>
  /* ── Toolbar ── */
  .toolbar {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    justify-content: space-between;
    padding: 4px 12px;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
    gap: var(--s2);
    position: relative;
    z-index: 20;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .toolbar::-webkit-scrollbar {
    display: none;
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 2px;
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
    flex-wrap: nowrap;
    justify-content: flex-end;
  }

  .format-toolbar {
    display: flex;
    align-items: center;
    gap: 2px;
    overflow-x: auto;
    scrollbar-width: none;
    min-width: 0;
  }
  .format-toolbar::-webkit-scrollbar {
    display: none;
  }

  .format-divider {
    width: 1px;
    height: 14px;
    background: var(--border);
    margin: 0 2px;
    flex-shrink: 0;
  }

  .stat {
    font-size: 10px;
    font-family: var(--font-mono);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .toolbar-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 7px;
    border: 1px solid var(--border);
    border-radius: var(--r);
    background: transparent;
    color: var(--text-secondary);
    font-size: 10px;
    font-family: var(--font-sans);
    cursor: pointer;
    transition: all var(--t-fast);
    white-space: nowrap;
  }
  .toolbar-btn:hover {
    background: var(--elevated);
    color: var(--text-primary);
  }
  .toolbar-btn.active {
    border-color: var(--text-secondary);
    color: var(--text-primary);
  }
  .toolbar-btn:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .save-btn {
    border-color: var(--accent);
    color: var(--accent);
  }
  .save-btn:hover {
    background: var(--accent);
    color: var(--accent-contrast-text, var(--bg));
  }
  .save-btn.saved {
    background: var(--success);
    border-color: var(--success);
    color: var(--text-primary);
  }

  .save-status {
    display: inline-block;
    min-width: 58px;
    text-align: center;
  }

  .danger-btn {
    color: var(--error);
    border-color: transparent;
  }
  .danger-btn:hover {
    border-color: var(--error);
    background: transparent;
  }

  /* ── Title ── */
  .toolbar-nav {
    margin-bottom: 0;
  }

  .nav-controls {
    display: flex;
    gap: 4px;
  }

  /* ── Unsaved Indicator ── */
  .unsaved-indicator {
    color: #fbbf24;
    font-size: 18px;
    font-weight: 700;
    line-height: 1;
    animation: pulse-dot 1.5s ease-in-out infinite;
  }

  @keyframes pulse-dot {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.3;
    }
  }
</style>
