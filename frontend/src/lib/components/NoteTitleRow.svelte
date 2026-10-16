<script lang="ts">
  import DynamicIcon from './DynamicIcon.svelte';
  import NoteIconSettingsModal from './NoteIconSettingsModal.svelte';
  import { activeIconPack } from '$lib/stores/settings';
  import { extractFrontmatter, getFileIcon } from '$lib/utils/fileTree';
  import { updateFrontmatterInContent } from '$lib/utils/noteContent';
  import type { Note } from '$lib/api';

  interface Props {
    note: Note | null;
    title: string;
    content: string;
    triggerAutosave: () => void;
    onContentChange: () => void;
    handleSave: () => void;
  }

  let {
    note,
    title = $bindable(),
    content = $bindable(),
    triggerAutosave,
    onContentChange,
    handleSave,
  }: Props = $props();

  let showIconSettings = $state(false);
  let customColor = $state('#ffffff');

  $effect(() => {
    const fm = extractFrontmatter(content || note?.content || '');
    customColor = fm.color || '#ffffff';
  });

  let iconMeta = $derived(extractFrontmatter(content || note?.content || ''));
  let noteIcon = $derived(
    iconMeta.icon || (note ? getFileIcon(note.title, content || note.content || '') : 'File')
  );
  let noteIconColor = $derived(iconMeta.color || undefined);
  let noteIconPack = $derived(iconMeta.pack || undefined);

  function pickIcon(ic: string) {
    updateFrontmatter('icon', ic);
    updateFrontmatter('iconPack', $activeIconPack);
  }

  function updateFrontmatter(key: string, value: string) {
    content = updateFrontmatterInContent(content, key, value);
    onContentChange();
    handleSave();
  }
</script>

<!-- Title -->
<div class="title-row">
  <button
    class="note-icon-btn"
    title="Personalizar icono"
    aria-label="Personalizar icono"
    type="button"
    onclick={() => (showIconSettings = true)}
  >
    <DynamicIcon name={noteIcon} size={16} color={noteIconColor} pack={noteIconPack} />
  </button>
  <input
    class="title-input"
    bind:value={title}
    placeholder="Título de la nota..."
    onkeydown={(e) => e.key === 'Enter' && handleSave()}
    oninput={triggerAutosave}
  />
</div>

<NoteIconSettingsModal
  bind:open={showIconSettings}
  bind:customColor
  {updateFrontmatter}
  {pickIcon}
/>

<style>
  .note-icon-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text-muted);
    cursor: pointer;
    flex-shrink: 0;
  }

  .note-icon-btn:hover {
    background: var(--elevated);
    color: var(--text-primary);
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
  .title-input::placeholder {
    color: var(--text-muted);
  }

  .title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 20px 24px 12px;
    border-bottom: 1px solid var(--border-light, var(--border));
    flex-shrink: 0;
  }
</style>
