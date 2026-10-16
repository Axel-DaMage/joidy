<script lang="ts">
  import { api } from '$lib/api';
  import LazyIconPicker from './LazyIconPicker.svelte';
  import TreeContextMenu from './TreeContextMenu.svelte';
  import FolderPicker from './FolderPicker.svelte';
  import { updateFolderMeta } from '$lib/stores/settings';
  import { updateNote } from '$lib/stores/notes';
  import {
    refreshTree,
    handleRename,
    confirmRename,
    handleMove,
    confirmMove,
    handleDeleteNote,
    handleNewNoteInFolder,
    handleDeleteFolder,
  } from '$lib/utils/notesPage';
  import {
    flatNodes,
    ctxMenu,
    renamingNode,
    renameValue,
    movingNode,
    editingFolder,
    editingFolderNote,
    folderColor,
    folderIcon,
    creatingFolder,
    newFolderName,
    newFolderParent,
    newFolderIcon,
    newFolderColor,
  } from '$lib/stores/notesUi';
  import { t } from 'svelte-i18n';
</script>

<!-- Folder customize modal -->
<!-- Create folder modal -->
{#if $creatingFolder}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="folder-modal-backdrop"
    role="dialog"
    tabindex="-1"
    onclick={() => ($creatingFolder = false)}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="folder-modal" onclick={(e) => e.stopPropagation()}>
      <h3 class="folder-modal-title">{$t('notesPage.createFolderTitle')}</h3>

      <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
        <span class="folder-label mono">{$t('notesPage.name')}</span>
        <input
          type="text"
          class="input mono"
          bind:value={$newFolderName}
          placeholder={$t('notesPage.newFolderPlaceholder')}
          style="width:100%; box-sizing:border-box;"
        />
      </div>

      <div style="display:flex; flex-direction:column; gap:4px; margin-bottom:12px;">
        <span class="folder-label mono">{$t('notesPage.location')}</span>
        <select
          class="input mono"
          bind:value={$newFolderParent}
          style="width:100%; box-sizing:border-box;"
        >
          <option value="">(Raíz)</option>
          {#each $flatNodes.filter((n) => n.type === 'folder') as f}
            <option value={f.path}>{f.path}</option>
          {/each}
        </select>
      </div>

      <div class="folder-color-row">
        <span class="folder-label mono">{$t('notesPage.color')}</span>
        <input type="color" class="folder-color-input" bind:value={$newFolderColor} />
        <input
          type="text"
          class="folder-hex-input mono"
          maxlength="7"
          bind:value={$newFolderColor}
        />
      </div>

      <div class="folder-icon-row">
        <span class="folder-label mono">{$t('notesPage.icon')}</span>
        <LazyIconPicker
          selected={$newFolderIcon}
          color={$newFolderColor}
          onSelect={(ic) => ($newFolderIcon = ic)}
        />
      </div>

      <div class="folder-modal-btns">
        <button onclick={() => ($creatingFolder = false)}>{$t('notesPage.cancel')}</button>
        <button
          class="primary"
          disabled={!$newFolderName.trim()}
          onclick={async () => {
            if (!$newFolderName.trim()) return;
            const targetPath = $newFolderParent
              ? `${$newFolderParent}/${$newFolderName.trim()}`
              : $newFolderName.trim();
            try {
              await api.folders.create(targetPath);
              updateFolderMeta(targetPath, { icon: $newFolderIcon, color: $newFolderColor });
              $creatingFolder = false;
              await refreshTree();
            } catch (e) {
              alert((e as any).message || 'Error al crear carpeta');
            }
          }}>{$t('notesPage.create')}</button
        >
      </div>
    </div>
  </div>
{/if}

{#key $ctxMenu}
  {#if $ctxMenu}
    <TreeContextMenu
      x={$ctxMenu.x}
      y={$ctxMenu.y}
      node={$ctxMenu.node}
      on:close={() => ($ctxMenu = null)}
      on:rename={handleRename}
      on:move={handleMove}
      on:deleteNote={handleDeleteNote}
      on:newNoteInFolder={handleNewNoteInFolder}
      on:deleteFolder={handleDeleteFolder}
    />
  {/if}
{/key}

{#if $renamingNode}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="folder-modal-backdrop"
    role="dialog"
    tabindex="-1"
    onclick={() => ($renamingNode = null)}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="folder-modal" onclick={(e) => e.stopPropagation()}>
      <h3 class="folder-modal-title">{$t('notesPage.renameTitle')}</h3>
      <input
        type="text"
        class="input mono"
        bind:value={$renameValue}
        style="width:100%; box-sizing:border-box; margin-bottom:12px;"
        onkeydown={(e) => e.key === 'Enter' && confirmRename()}
      />
      <div class="folder-modal-btns">
        <button onclick={() => ($renamingNode = null)}>{$t('notesPage.cancel')}</button>
        <button class="primary" disabled={!$renameValue.trim()} onclick={confirmRename}
          >{$t('notesPage.save')}</button
        >
      </div>
    </div>
  </div>
{/if}

{#if $movingNode}
  <FolderPicker
    flatNodes={$flatNodes}
    on:close={() => ($movingNode = null)}
    on:select={(e) => confirmMove(e.detail)}
  />
{/if}

{#if $editingFolder}
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <div
    class="folder-modal-backdrop"
    role="dialog"
    tabindex="-1"
    onclick={() => ($editingFolder = null)}
  >
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="folder-modal" onclick={(e) => e.stopPropagation()}>
      <h3 class="folder-modal-title">{$t('notesPage.customizeFolderTitle')}</h3>

      <!-- Color bar -->
      <div class="folder-color-row">
        <span class="folder-label mono">{$t('notesPage.color')}</span>
        <input type="color" class="folder-color-input" bind:value={$folderColor} />
        <input type="text" class="folder-hex-input mono" maxlength="7" bind:value={$folderColor} />
      </div>

      <!-- Icon picker -->
      <div class="folder-icon-row">
        <span class="folder-label mono">{$t('notesPage.icon')}</span>
        <LazyIconPicker
          selected={$folderIcon}
          color={$folderColor}
          onSelect={(ic) => ($folderIcon = ic)}
        />
      </div>

      <div class="folder-modal-btns">
        <button onclick={() => ($editingFolder = null)}>{$t('notesPage.cancel')}</button>
        <button
          onclick={async () => {
            if ($editingFolder) {
              updateFolderMeta($editingFolder, { icon: $folderIcon, color: $folderColor });
              if ($editingFolderNote) {
                let content = $editingFolderNote.content;
                const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
                if (match) {
                  let yaml = match[1];
                  if (yaml.match(/(?:^|\n)icon:\s*([^\n]*)/)) {
                    yaml = yaml.replace(/((?:^|\n)icon:\s*)([^\n]*)/, `$1${$folderIcon}`);
                  } else {
                    yaml += `\nicon: ${$folderIcon}`;
                  }
                  if (yaml.match(/(?:^|\n)iconColor:\s*([^\n]*)/)) {
                    yaml = yaml.replace(/((?:^|\n)iconColor:\s*)([^\n]*)/, `$1${$folderColor}`);
                  } else {
                    yaml += `\niconColor: ${$folderColor}`;
                  }
                  content = content.replace(/^---\r?\n([\s\S]*?)\r?\n---/, `---\n${yaml}\n---`);
                } else {
                  content = `---\nicon: ${$folderIcon}\niconColor: ${$folderColor}\n---\n\n${content}`;
                }
                await updateNote($editingFolderNote.id, { content });
              }
            }
            $editingFolder = null;
            $editingFolderNote = null;
          }}>{$t('notesPage.save')}</button
        >
      </div>
    </div>
  </div>
{/if}

<style>
  /* Folder customize modal */
  .folder-modal-backdrop {
    position: fixed;
    top: 50px;
    bottom: 50px;
    left: 0;
    right: 0;
    z-index: var(--z-overlay);
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .folder-modal {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    width: 100%;
    height: 100%;
    max-width: 800px;
    min-height: 0;
  }
  .folder-modal-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
  .folder-label {
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .folder-color-row {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }
  .folder-color-input {
    flex: 1;
    height: 28px;
    border: 1px solid var(--border);
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
    background: none;
  }
  .folder-color-input::-webkit-color-swatch-wrapper {
    padding: 0;
  }
  .folder-color-input::-webkit-color-swatch {
    border: none;
    border-radius: 3px;
  }
  .folder-hex-input {
    width: 75px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text-primary);
    font-size: 11px;
    text-align: center;
    text-transform: uppercase;
  }
  .folder-icon-row {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    min-height: 0;
  }
  :global(.folder-icon-header) {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  :global(.folder-search-row) {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 10px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  :global(.folder-search-input) {
    background: transparent;
    border: none;
    outline: none;
    font-size: 12px;
    color: var(--text-primary);
    width: 100%;
  }
  :global(.folder-search-input)::placeholder {
    color: var(--text-muted);
  }
  :global(.no-icons-msg) {
    grid-column: 1 / -1;
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
    padding: 20px;
  }
  :global(.folder-icon-list) {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: 6px;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    align-content: start;
  }
  :global(.folder-icon-btn) {
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border-light);
    border-radius: 6px;
    background: var(--bg);
    color: var(--text-muted);
    cursor: pointer;
    transition: all var(--t-fast);
  }
  :global(.folder-icon-btn):hover {
    border-color: var(--border);
    color: var(--text-primary);
  }
  .folder-modal-btns {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }
  .folder-modal-btns button {
    flex: 1;
    padding: 8px;
    border-radius: 5px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid var(--border);
    background: var(--bg);
    color: var(--text-secondary);
  }
  .folder-modal-btns button:first-child:hover {
    border-color: var(--text-muted);
    color: var(--text-primary);
  }
  .folder-modal-btns button:last-child {
    background: var(--xp);
    border-color: var(--xp);
    color: var(--xp-contrast-text, var(--bg));
  }
  .folder-modal-btns button:last-child:hover {
    opacity: 0.85;
  }
</style>
