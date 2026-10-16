<script lang="ts">
  import ModalDialog from './ModalDialog.svelte';
  import { selectedNoteIds } from '$lib/stores/notes';
  import { confirmDelete } from '$lib/utils/notesPage';
  import { deleteModalOpen, deleteMode } from '$lib/stores/notesUi';
  import { t } from 'svelte-i18n';
</script>

{#if $deleteModalOpen}
  <ModalDialog
    open={true}
    title={$deleteMode === 'bulk'
      ? `¿Eliminar ${$selectedNoteIds.size} nota${$selectedNoteIds.size !== 1 ? 's' : ''}?`
      : $t('notesPage.delete')}
    size="sm"
    onClose={() => ($deleteModalOpen = false)}
  >
    <p class="delete-modal-desc">{$t('notesPage.deleteHint')}</p>
    <div class="delete-modal-actions">
      <button class="btn btn-ghost" onclick={() => ($deleteModalOpen = false)}
        >{$t('notesPage.cancel')}</button
      >
      <button class="btn btn-danger" onclick={confirmDelete}>{$t('notesPage.delete')}</button>
    </div>
  </ModalDialog>
{/if}

<style>
  /* Styles moved from NotesOverlays.svelte when the modal was extracted
     into its own component (#210) — scoped styles don't cross component
     boundaries, so they must live where the markup is. */
  .delete-modal-desc {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0 0 16px 0;
    line-height: 1.5;
  }
  .delete-modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }
  .delete-modal-actions .btn-danger {
    background: var(--error);
    border-color: var(--error);
    color: #fff;
  }
  .delete-modal-actions .btn-danger:hover {
    opacity: 0.85;
  }
</style>
